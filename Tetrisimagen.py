import streamlit as st
from PIL import Image, ImageChops, ImageFilter, ImageDraw
import io
import random

# Configuração da Folha A4 em 300 DPI
A4_WIDTH = 2480
A4_HEIGHT = 3508
MM_TO_PX = 11.81

def gerar_contorno_profissional(img, sangria_mm, espessura_linha):
    """Cria sangria branca sólida, sem furos internos e com curvas lisas"""
    sangria_px = int(sangria_mm * MM_TO_PX)
    # 1. Obter a máscara alfa e garantir que seja binária (preto e branco total)
    alpha = img.split()[3].point(lambda p: 255 if p > 0 else 0)
    
    # 2. FECHAR BURACOS INTERNOS (Estratégia de Inundação)
    # Criamos uma máscara um pouco maior para garantir que não haja furos
    mask_contorno = alpha.filter(ImageFilter.MaxFilter(sangria_px * 2 + 1))
    
    # Técnica de Flood Fill para garantir que o interior seja 100% branco
    # Preenchemos a partir das bordas (0,0) para identificar o que é fundo externo
    bg = Image.new("L", (mask_contorno.width + 2, mask_contorno.height + 2), 0)
    bg.paste(mask_contorno, (1, 1))
    ImageDraw.floodfill(bg, (0, 0), 255)
    # Invertemos para obter apenas o interior preenchido
    mask_solida = ImageOps.invert(bg.crop((1, 1, mask_contorno.width + 1, mask_contorno.height + 1)))
    # Somamos a máscara original com a sólida
    mask_final = ImageChops.screen(mask_contorno, mask_solida)

    # 3. SUAVIZAÇÃO GAUSSIANA (Eliminar "Colinas" e degraus)
    mask_final = mask_final.filter(ImageFilter.GaussianBlur(radius=5))
    mask_final = mask_final.point(lambda p: 255 if p > 128 else 0)

    # 4. CRIAR A LINHA PRETA DO SCANNER
    mask_linha = mask_final.filter(ImageFilter.MaxFilter(espessura_linha * 2 + 1))
    
    # Montagem Final
    peca = Image.new("RGBA", img.size, (0, 0, 0, 0))
    preto = Image.new("RGBA", img.size, (0, 0, 0, 255))
    branco = Image.new("RGBA", img.size, (255, 255, 255, 255))
    
    peca.paste(preto, (0, 0), mask_linha)   # Linha externa
    peca.paste(branco, (0, 0), mask_final)  # Sangria branca sólida
    peca.paste(img, (0, 0), img)            # Imagem original
    
    return peca, mask_linha

from PIL import ImageOps # Necessário para o Invert

def montar_folha_final(lista_config, margem_mm, sangria_mm, espaco_mm, espessura_linha):
    canvas = Image.new('RGBA', (A4_WIDTH, A4_HEIGHT), (255, 255, 255, 255))
    mask_canvas = Image.new('L', (A4_WIDTH, A4_HEIGHT), 0)
    margem_px = int(margem_mm * MM_TO_PX)
    espaco_px = int(espaco_mm * MM_TO_PX)
    
    processed = []
    for item in lista_config:
        img_orig = item['img'].convert("RGBA")
        w_px = int(item['width_mm'] * MM_TO_PX)
        ratio = w_px / img_orig.size[0]
        img_res = img_orig.resize((w_px, int(img_orig.size[1] * ratio)), Image.LANCZOS)
        
        bbox = img_res.getbbox()
        if bbox: img_res = img_res.crop(bbox)
            
        img_com_contorno, mask_c = gerar_contorno_profissional(img_res, sangria_mm, espessura_linha)
        
        m_colisao = mask_c.filter(ImageFilter.MaxFilter(espaco_px * 2 + 1)) if espaco_px > 0 else mask_c
        processed.append({'img': img_com_contorno, 'mask': m_colisao})

    processed.sort(key=lambda x: x['img'].size[1], reverse=True)

    for p in processed:
        img, m = p['img'], p['mask']
        iw, ih = img.size
        sucesso = False
        for _ in range(5000): 
            tx = random.randint(margem_px, A4_WIDTH - iw - margem_px)
            ty = random.randint(margem_px, A4_HEIGHT - ih - margem_px)
            pedaco = mask_canvas.crop((tx, ty, tx + iw, ty + ih))
            if not ImageChops.multiply(pedaco, m).getbbox():
                canvas.paste(img, (tx, ty), img)
                mask_canvas.paste(m, (tx, ty), m)
                sucesso = True
                break
    return canvas

# --- INTERFACE ---
st.set_page_config(page_title="ScanNCut Final Pro", layout="wide")
st.title("✂️ ScanNCut: Contorno Sólido e Suave")

sangria = st.sidebar.number_input("Sangria (mm)", 0.5, 10.0, 3.0, 0.5)
espaco = st.sidebar.number_input("Espaço entre Peças (mm)", 0.0, 10.0, 1.0, 0.5)
linha = st.sidebar.slider("Linha do Scanner (px)", 1, 5, 2)
margem = st.sidebar.slider("Margem Folha (mm)", 5, 30, 10)

arquivos = st.file_uploader("Suba seus PNGs", type=['png'], accept_multiple_files=True)

if arquivos:
    config_list = []
    cols = st.columns(4)
    for i, arq in enumerate(arquivos):
        with cols[i % 4]:
            img = Image.open(arq)
            st.image(img, use_container_width=True)
            w = st.number_input(f"Largura (mm):", 10, 250, 80, key=f"w_{i}")
            config_list.append({'img': img, 'width_mm': w})

    if st.button("🚀 GERAR FOLHA PERFEITA"):
        with st.spinner('Limpando vãos e suavizando curvas...'):
            folha = montar_folha_final(config_list, margem, sangria, espaco, linha)
            st.image(folha, use_container_width=True)
            buf = io.BytesIO()
            folha.convert("RGB").save(buf, format="PDF", resolution=300.0)
            st.download_button("📥 Baixar PDF", buf.getvalue(), "folha_final.pdf")
