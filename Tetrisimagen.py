import streamlit as st
from PIL import Image, ImageChops, ImageFilter, ImageDraw, ImageOps
import io
import random

# Configuração da Folha A4 em 300 DPI
A4_WIDTH = 2480
A4_HEIGHT = 3508
MM_TO_PX = 11.81

def gerar_contorno_bolha_total(img, sangria_mm, espessura_linha):
    """Cria uma bolha branca sólida e arredondada sem nenhum furo interno"""
    sangria_px = int(sangria_mm * MM_TO_PX)
    
    # 1. Criar máscara binária básica
    alpha = img.split()[3].point(lambda p: 255 if p > 50 else 0)
    
    # 2. TRANSFORMAR EM BOLHA SÓLIDA
    # Dilatamos muito para fechar qualquer vão entre rabo/perna/braço
    mask_bolha = alpha.filter(ImageFilter.MaxFilter(25)) 
    
    # Preenchimento de inundação (Flood Fill) para garantir que o interior seja 100% branco
    bg = Image.new("L", (mask_bolha.width + 2, mask_bolha.height + 2), 0)
    bg.paste(mask_bolha, (1, 1))
    ImageDraw.floodfill(bg, (0, 0), 255)
    mask_solida = ImageOps.invert(bg.crop((1, 1, mask_bolha.width + 1, mask_bolha.height + 1)))
    
    # 3. SUAVIZAÇÃO EXTREMA (Para curvas lisas como o exemplo de Natal)
    # Expandimos para o tamanho da sangria real
    mask_final = mask_solida.filter(ImageFilter.MaxFilter(sangria_px))
    # Aplicamos um desfoque forte e depois binarizamos para arredondar tudo
    mask_final = mask_final.filter(ImageFilter.GaussianBlur(radius=12))
    mask_final = mask_final.point(lambda p: 255 if p > 128 else 0)

    # 4. LINHA PRETA DE CORTE
    mask_linha = mask_final.filter(ImageFilter.MaxFilter(espessura_linha * 2 + 1))
    
    # Montagem Final
    peca = Image.new("RGBA", img.size, (0, 0, 0, 0))
    preto = Image.new("RGBA", img.size, (0, 0, 0, 255))
    branco = Image.new("RGBA", img.size, (255, 255, 255, 255))
    
    peca.paste(preto, (0, 0), mask_linha)   # Borda preta externa
    peca.paste(branco, (0, 0), mask_final)  # Sangria branca sólida
    peca.paste(img, (0, 0), img)            # Desenho no topo
    
    return peca, mask_linha

def montar_folha_scanncut(lista_config, margem_mm, sangria_mm, espaco_mm, linha_px):
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
        
        # Limpa bordas vazias
        bbox = img_res.getbbox()
        if bbox: img_res = img_res.crop(bbox)
            
        img_c, mask_c = gerar_contorno_bolha_total(img_res, sangria_mm, linha_px)
        
        m_col = mask_c.filter(ImageFilter.MaxFilter(espaco_px * 2 + 1)) if espaco_px > 0 else mask_c
        processed.append({'img': img_c, 'mask': m_col})

    processed.sort(key=lambda x: x['img'].size[1], reverse=True)

    for p in processed:
        img, m = p['img'], p['mask']
        iw, ih = img.size
        for _ in range(5000): 
            tx = random.randint(margem_px, A4_WIDTH - iw - margem_px)
            ty = random.randint(margem_px, A4_HEIGHT - ih - margem_px)
            if not ImageChops.multiply(mask_canvas.crop((tx, ty, tx + iw, ty + ih)), m).getbbox():
                canvas.paste(img, (tx, ty), img)
                mask_canvas.paste(m, (tx, ty), m)
                break
    return canvas

# Interface
st.set_page_config(page_title="Modo Bolha ScanNCut", layout="wide")
st.title("✂️ Modo Bolha: Contorno Sólido e Redondo")

sangria = st.sidebar.slider("Tamanho da Sangria (mm)", 1.0, 15.0, 4.0)
espaco = st.sidebar.slider("Espaço entre Peças (mm)", 0.0, 10.0, 1.0)
linha = st.sidebar.slider("Linha do Scanner (px)", 1, 5, 2)

arquivos = st.file_uploader("Upload PNGs", type=['png'], accept_multiple_files=True)

if arquivos:
    config_list = []
    cols = st.columns(4)
    for i, arq in enumerate(arquivos):
        with cols[i % 4]:
            img = Image.open(arq)
            st.image(img, use_container_width=True)
            w = st.number_input(f"Largura (mm):", 10, 250, 80, key=f"w_{i}")
            config_list.append({'img': img, 'width_mm': w})

    if st.button("🚀 GERAR FOLHA BOLHA SÓLIDA"):
        with st.spinner('Criando silhuetas redondas...'):
            folha = montar_folha_scanncut(config_list, 10, sangria, espaco, linha)
            st.image(folha, use_container_width=True)
            buf = io.BytesIO()
            folha.convert("RGB").save(buf, format="PDF", resolution=300.0)
            st.download_button("📥 Baixar PDF Perfeito", buf.getvalue(), "folha_bolha_perfeita.pdf")
