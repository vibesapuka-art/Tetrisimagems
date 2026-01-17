import streamlit as st
from PIL import Image, ImageChops, ImageFilter, ImageDraw, ImageOps
import io
import random

# Configuração da Folha A4 em 300 DPI
A4_WIDTH = 2480
A4_HEIGHT = 3508
MM_TO_PX = 11.81

def gerar_contorno_bolha_limpa(img, sangria_mm, espessura_linha):
    """Cria uma bolha sólida, remove sujeiras e bolinhas internas"""
    sangria_px = int(sangria_mm * MM_TO_PX)
    
    # 1. Criar máscara binária e remover ruídos pequenos (bolinhas)
    alpha = img.split()[3].point(lambda p: 255 if p > 100 else 0)
    # Filtro para eliminar pixels isolados (sujeira)
    alpha = alpha.filter(ImageFilter.MedianFilter(size=7))
    
    # 2. UNIFICAR SILHUETA (Fechar vãos entre rabo e pernas)
    # Usamos uma expansão para 'colar' as partes próximas
    mask_unificada = alpha.filter(ImageFilter.MaxFilter(21))
    
    # 3. PREENCHIMENTO TOTAL (Flood Fill)
    # Garante que o interior seja uma massa branca única
    bg = Image.new("L", (mask_unificada.width + 2, mask_unificada.height + 2), 0)
    bg.paste(mask_unificada, (1, 1))
    ImageDraw.floodfill(bg, (0, 0), 255)
    mask_solida = ImageOps.invert(bg.crop((1, 1, mask_unificada.width + 1, mask_unificada.height + 1)))
    
    # 4. SUAVIZAÇÃO E SANGRIA (Estilo Natal)
    mask_final = mask_solida.filter(ImageFilter.MaxFilter(sangria_px))
    # Desfoque alto para arredondar tudo
    mask_final = mask_final.filter(ImageFilter.GaussianBlur(radius=10))
    mask_final = mask_final.point(lambda p: 255 if p > 128 else 0)

    # 5. LINHA PRETA DE CORTE EXTERNA
    mask_linha = mask_final.filter(ImageFilter.MaxFilter(espessura_linha * 2 + 1))
    
    # Montagem
    peca = Image.new("RGBA", img.size, (0, 0, 0, 0))
    preto = Image.new("RGBA", img.size, (0, 0, 0, 255))
    branco = Image.new("RGBA", img.size, (255, 255, 255, 255))
    
    peca.paste(preto, (0, 0), mask_linha)
    peca.paste(branco, (0, 0), mask_final)
    peca.paste(img, (0, 0), img)
    
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
        
        bbox = img_res.getbbox()
        if bbox: img_res = img_res.crop(bbox)
            
        img_c, mask_c = gerar_contorno_bolha_limpa(img_res, sangria_mm, linha_px)
        
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
st.set_page_config(page_title="ScanNCut Bubble Clean", layout="wide")
st.title("✂️ Modo Bolha Limpa (Sem Ruídos)")

sangria = st.sidebar.slider("Tamanho da Sangria (mm)", 1.0, 15.0, 4.5)
espaco = st.sidebar.slider("Espaço entre Peças (mm)", 0.0, 10.0, 1.5)
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

    if st.button("🚀 GERAR PDF SEM BURACOS"):
        with st.spinner('Limpando ruídos e unificando contorno...'):
            folha = montar_folha_scanncut(config_list, 10, sangria, espaco, linha)
            st.image(folha, use_container_width=True)
            buf = io.BytesIO()
            folha.convert("RGB").save(buf, format="PDF", resolution=300.0)
            st.download_button("📥 Baixar PDF Limpo", buf.getvalue(), "folha_bolha_limpa.pdf")
