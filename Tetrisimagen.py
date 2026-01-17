import streamlit as st
from PIL import Image, ImageChops, ImageFilter
import io
import random

# Configuração da Folha A4 em 300 DPI
A4_WIDTH = 2480
A4_HEIGHT = 3508
MM_TO_PX = 11.81

def verificar_colisao_binaria(mask_canvas, img_mask, pos):
    """Verifica se há sobreposição de pixels brancos (ocupados)"""
    x, y = pos
    iw, ih = img_mask.size
    # Recorta o pedaço da máscara da folha na posição desejada
    pedaco_mask = mask_canvas.crop((x, y, x + iw, y + ih))
    # Se houver qualquer pixel branco (255) em comum, deu colisão
    colisao = ImageChops.multiply(pedaco_mask, img_mask)
    return colisao.getbbox() is not None

def montar_folha_organica(lista_imgs, margin_mm, spacing_mm):
    canvas = Image.new('RGBA', (A4_WIDTH, A4_HEIGHT), (255, 255, 255, 255))
    mask_canvas = Image.new('L', (A4_WIDTH, A4_HEIGHT), 0) # Mapa de ocupação
    
    margin_px = int(margin_mm * MM_TO_PX)
    spacing_px = int(spacing_mm * MM_TO_PX)
    
    processed = []
    for item in lista_imgs:
        img = item['img'].convert("RGBA")
        target_w_px = int(item['width_mm'] * MM_TO_PX)
        # Redimensionamento
        w_orig, h_orig = img.size
        ratio = target_w_px / w_orig
        img_res = img.resize((target_w_px, int(h_orig * ratio)), Image.LANCZOS)
        
        # Crop para remover bordas vazias
        bbox = img_res.getbbox()
        if bbox: img_res = img_res.crop(bbox)
        
        # Máscara binária da imagem (255 onde tem cor)
        m = img_res.split()[3].point(lambda p: 255 if p > 50 else 0)
        # Aplica o espaçamento (engrossa a máscara)
        if spacing_px > 0:
            m = m.filter(ImageFilter.MaxFilter(spacing_px * 2 + 1))
            
        processed.append({'img': img_res, 'mask': m})

    # Maiores primeiro para ocupar os espaços principais
    processed.sort(key=lambda x: x['img'].size[1], reverse=True)

    for p in processed:
        img, m = p['img'], p['mask']
        iw, ih = img.size
        sucesso = False
        
        # Tenta 2000 posições aleatórias para cada peça para achar um vão
        for _ in range(2000):
            tx = random.randint(margin_px, A4_WIDTH - iw - margin_px)
            ty = random.randint(margin_px, A4_HEIGHT - ih - margin_px)
            
            if not verificar_colisao_binaria(mask_canvas, m, (tx, ty)):
                canvas.paste(img, (tx, ty), img)
                mask_canvas.paste(m, (tx, ty), m)
                sucesso = True
                break
        
        if not sucesso:
            st.error(f"Não encontrei um vão para a imagem de {iw}px de largura.")

    return canvas

st.set_page_config(page_title="App Papelaria - Encaixe Orgânico", layout="wide")
st.title("🧩 Encaixe nos Vãos (Modo Aleatório)")

st.sidebar.header("Configurações")
margem = st.sidebar.slider("Margem da Folha (mm)", 0, 30, 5)
espaco = st.sidebar.slider("Folga entre peças (mm)", 0, 10, 1)

arquivos = st.file_uploader("Upload PNGs", type=['png'], accept_multiple_files=True)

if arquivos:
    config = []
    cols = st.columns(4)
    for i, arq in enumerate(arquivos):
        with cols[i % 4]:
            img = Image.open(arq)
            st.image(img, use_container_width=True)
            w = st.number_input(f"Largura (mm):", 10, 250, 75, key=f"w_{i}")
            config.append({'img': img, 'width_mm': w})

    if st.button("🎲 GERAR POSIÇÕES NOS VÃOS"):
        with st.spinner('Procurando buracos na folha...'):
            folha = montar_folha_organica(config, margem, espaco)
            st.image(folha, use_container_width=True)
            
            pdf_buf = io.BytesIO()
            folha.convert("RGB").save(pdf_buf, format="PDF", resolution=300.0)
            st.download_button("📥 Baixar PDF Montado", pdf_buf.getvalue(), "folha_vaos.pdf")
