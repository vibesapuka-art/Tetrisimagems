import streamlit as st
from PIL import Image, ImageChops, ImageFilter, ImageDraw, ImageOps
import io
import random

# Configuração A4 300 DPI
A4_WIDTH = 2480
A4_HEIGHT = 3508
MM_TO_PX = 11.81

def gerar_contorno_custom(img, sangria_mm, suavidade, linha_ativa, espessura_linha):
    """Gera contorno com níveis de suavidade e opção de linha liga/desliga"""
    sangria_px = int(sangria_mm * MM_TO_PX)
    alpha = img.split()[3].point(lambda p: 255 if p > 100 else 0)
    
    # Ajuste de níveis
    if suavidade == "Baixa":
        raio_blur = 3
        expansao_uniao = 5
    elif suavidade == "Média":
        raio_blur = 8
        expansao_uniao = 15
    else: # Alta
        raio_blur = 15
        expansao_uniao = 30

    # 1. Unificar silhueta e fechar buracos
    mask_base = alpha.filter(ImageFilter.MaxFilter(expansao_uniao))
    bg = Image.new("L", (mask_base.width + 2, mask_base.height + 2), 0)
    bg.paste(mask_base, (1, 1))
    ImageDraw.floodfill(bg, (0, 0), 255)
    mask_solida = ImageOps.invert(bg.crop((1, 1, mask_base.width + 1, mask_base.height + 1)))
    
    # 2. Criar Sangria e Suavizar
    mask_sangria = mask_solida.filter(ImageFilter.MaxFilter(sangria_px))
    mask_sangria = mask_sangria.filter(ImageFilter.GaussianBlur(radius=raio_blur))
    mask_sangria = mask_sangria.point(lambda p: 255 if p > 128 else 0)

    # 3. Montagem
    nova_img = Image.new("RGBA", img.size, (0, 0, 0, 0))
    branco = Image.new("RGBA", img.size, (255, 255, 255, 255))
    
    if linha_ativa:
        mask_linha = mask_sangria.filter(ImageFilter.MaxFilter(espessura_linha * 2 + 1))
        preto = Image.new("RGBA", img.size, (0, 0, 0, 255))
        nova_img.paste(preto, (0, 0), mask_linha)
        mask_final_colisao = mask_linha
    else:
        mask_final_colisao = mask_sangria

    nova_img.paste(branco, (0, 0), mask_sangria)
    nova_img.paste(img, (0, 0), img)
    
    return nova_img, mask_final_colisao

def montar_folha(lista_config, margem_mm, sangria_mm, espaco_mm, suavidade, linha_ativa, linha_px):
    canvas = Image.new('RGBA', (A4_WIDTH, A4_HEIGHT), (255, 255, 255, 255))
    mask_canvas = Image.new('L', (A4_WIDTH, A4_HEIGHT), 0)
    margem_px = int(margem_mm * MM_TO_PX)
    espaco_px = int(espaco_mm * MM_TO_PX)
    
    processed = []
    for item in lista_config:
        img_res = item['img'].convert("RGBA")
        w_px = int(item['width_mm'] * MM_TO_PX)
        ratio = w_px / img_res.size[0]
        img_res = img_res.resize((w_px, int(img_res.size[1] * ratio)), Image.LANCZOS)
        
        bbox = img_res.getbbox()
        if bbox: img_res = img_res.crop(bbox)
            
        peca, m_c = gerar_contorno_custom(img_res, sangria_mm, suavidade, linha_ativa, linha_px)
        m_col = m_c.filter(ImageFilter.MaxFilter(espaco_px * 2 + 1)) if espaco_px > 0 else m_c
        processed.append({'img': peca, 'mask': m_col})

    processed.sort(key=lambda x: x['img'].size[1], reverse=True)
    for p in processed:
        img, m = p['img'], p['mask']
        iw, ih = img.size
        for _ in range(3000): 
            tx = random.randint(margem_px, A4_WIDTH - iw - margem_px)
            ty = random.randint(margem_px, A4_HEIGHT - ih - margem_px)
            if not ImageChops.multiply(mask_canvas.crop((tx, ty, tx + iw, ty + ih)), m).getbbox():
                canvas.paste(img, (tx, ty), img)
                mask_canvas.paste(m, (tx, ty), m)
                break
    return canvas

# Interface
st.set_page_config(page_title="ScanNCut Studio", layout="wide")
st.title("✂️ Organizador de Topos Profissional")

# Sidebar organizada
st.sidebar.header("🎨 Estilo do Contorno")
sangria_mm = st.sidebar.slider("Tamanho da Sangria (mm)", 0.0, 15.0, 3.0)
suavidade = st.sidebar.select_slider("Suavidade do Contorno", options=["Baixa", "Média", "Alta"], value="Média")

st.sidebar.header("🛠️ Opções de Linha")
linha_ativa = st.sidebar.checkbox("Ativar Contorno Preto (Scanner)", value=True)
linha_px = st.sidebar.slider("Espessura da Linha (px)", 1, 5, 2)

st.sidebar.header("📏 Layout")
espaco_mm = st.sidebar.slider("Espaço entre peças (mm)", 0.0, 10.0, 1.0)
margem_folha = st.sidebar.slider("Margem da folha (mm)", 5, 20, 10)

arquivos = st.file_uploader("Suba seus personagens PNG", type=['png'], accept_multiple_files=True)

if arquivos:
    config_list = []
    # Grid com imagens menores no visor
    cols = st.columns(6) 
    for i, arq in enumerate(arquivos):
        with cols[i % 6]:
            img = Image.open(arq)
            # Preview pequeno para não poluir
            st.image(img, width=100) 
            w = st.number_input(f"L (mm)", 10, 250, 70, key=f"w_{i}")
            config_list.append({'img': img, 'width_mm': w})

    if st.button("🚀 GERAR FOLHA"):
        with st.spinner('Processando...'):
            folha = montar_folha(config_list, margem_folha, sangria_mm, espaco_mm, suavidade, linha_ativa, linha_px)
            st.image(folha, use_container_width=True)
            buf = io.BytesIO()
            folha.convert("RGB").save(buf, format="PDF", resolution=300.0)
            st.download_button("📥 Baixar PDF", buf.getvalue(), "folha_topo.pdf")
