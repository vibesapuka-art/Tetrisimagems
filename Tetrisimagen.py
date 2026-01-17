import streamlit as st
from PIL import Image, ImageChops, ImageFilter, ImageDraw, ImageOps
import io
import random

# Configuração da Folha A4 em 300 DPI
A4_WIDTH = 2480
A4_HEIGHT = 3508
MM_TO_PX = 11.81

def gerar_contorno_bolha(img, sangria_mm, espessura_linha):
    """Cria uma bolha sólida sem furos internos e com curvas arredondadas"""
    sangria_px = int(sangria_mm * MM_TO_PX)
    
    # 1. Criar máscara binária (Preto e Branco total)
    alpha = img.split()[3].point(lambda p: 255 if p > 30 else 0)
    
    # 2. FECHAR BURACOS INTERNOS (Inundação Total)
    # Expandimos um pouco para unir partes próximas (como o rabo e a perna)
    mask_expandida = alpha.filter(ImageFilter.MaxFilter(15))
    
    # Preenchimento de inundação (Flood Fill) para garantir que não existam ilhas ou buracos
    bg = Image.new("L", (mask_expandida.width + 2, mask_expandida.height + 2), 0)
    bg.paste(mask_expandida, (1, 1))
    ImageDraw.floodfill(bg, (0, 0), 255)
    # Invertemos para ter a silhueta 100% preenchida por dentro
    mask_solida = ImageOps.invert(bg.crop((1, 1, mask_expandida.width + 1, mask_expandida.height + 1)))
    
    # 3. CRIAR A SANGRIA E SUAVIZAR (Fim das colinas/serrotes)
    mask_sangria = mask_solida.filter(ImageFilter.MaxFilter(sangria_px * 2 + 1))
    # Suavização pesada para criar curvas orgânicas
    mask_sangria = mask_sangria.filter(ImageFilter.GaussianBlur(radius=8))
    mask_sangria = mask_sangria.point(lambda p: 255 if p > 120 else 0)

    # 4. CRIAR A LINHA PRETA DE CORTE PARA O SCANNER
    mask_linha = mask_sangria.filter(ImageFilter.MaxFilter(espessura_linha * 2 + 1))
    
    # Montagem Final: Linha -> Sangria Branca -> Personagem
    peca_final = Image.new("RGBA", img.size, (0, 0, 0, 0))
    preto = Image.new("RGBA", img.size, (0, 0, 0, 255))
    branco = Image.new("RGBA", img.size, (255, 255, 255, 255))
    
    peca_final.paste(preto, (0, 0), mask_linha)
    peca_final.paste(branco, (0, 0), mask_sangria)
    peca_final.paste(img, (0, 0), img)
    
    return peca_final, mask_linha

def montar_folha_final(lista_config, margem_mm, sangria_mm, espaco_mm, linha_px):
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
        
        # Gera o contorno estilo bolha sólida
        peca, mask_c = gerar_contorno_bolha(img_res, sangria_mm, linha_px)
        
        m_colisao = mask_c.filter(ImageFilter.MaxFilter(espaco_px * 2 + 1)) if espaco_px > 0 else mask_c
        processed.append({'img': peca, 'mask': m_colisao})

    # Algoritmo de encaixe aleatório para preencher vãos
    processed.sort(key=lambda x: x['img'].size[1], reverse=True)
    for p in processed:
        img, m = p['img'], p['mask']
        iw, ih = img.size
        sucesso = False
        for _ in range(5000): 
            tx = random.randint(margem_px, A4_WIDTH - iw - margem_px)
            ty = random.randint(margem_px, A4_HEIGHT - ih - margem_px)
            if not ImageChops.multiply(mask_canvas.crop((tx, ty, tx + iw, ty + ih)), m).getbbox():
                canvas.paste(img, (tx, ty), img)
                mask_canvas.paste(m, (tx, ty), m)
                sucesso = True
                break
    return canvas

# Interface Streamlit
st.set_page_config(page_title="ScanNCut Bubble Mode", layout="wide")
st.title("🎯 Contorno Sólido Profissional (Modo Bolha)")

st.sidebar.header("Ajustes de Corte")
sangria_val = st.sidebar.slider("Tamanho da Sangria Branca (mm)", 1.0, 10.0, 3.5)
espaco_val = st.sidebar.slider("Distância entre Peças (mm)", 0.0, 10.0, 1.0)
linha_val = st.sidebar.slider("Espessura da Linha Preta (px)", 1, 5, 2)
margem_val = st.sidebar.slider("Margem da Folha (mm)", 5, 30, 10)

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

    if st.button("🚀 GERAR FOLHA COM CONTORNO LISO"):
        with st.spinner('Preenchendo silhuetas e suavizando curvas...'):
            folha = montar_folha_final(config_list, margem_val, sangria_val, espaco_val, linha_val)
            st.image(folha, use_container_width=True)
            buf = io.BytesIO()
            folha.convert("RGB").save(buf, format="PDF", resolution=300.0)
            st.download_button("📥 Baixar PDF", buf.getvalue(), "folha_perfeita.pdf")
