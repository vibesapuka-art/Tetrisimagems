import streamlit as st
from PIL import Image, ImageChops, ImageFilter, ImageOps
import io
import random

# Configuração da Folha A4 em 300 DPI
A4_WIDTH = 2480
A4_HEIGHT = 3508
MM_TO_PX = 11.81

def criar_contorno(img, offset_px):
    """Cria uma borda branca ao redor da imagem transparente"""
    # Extrai o canal alpha (transparência)
    alpha = img.split()[3]
    # Engorda o alpha para criar o contorno
    mask = alpha.filter(ImageFilter.MaxFilter(offset_px * 2 + 1))
    
    # Cria um fundo branco com o novo formato da máscara
    contorno = Image.new("RGBA", img.size, (255, 255, 255, 255))
    contorno.putalpha(mask)
    
    # Cola a imagem original por cima do contorno branco
    contorno.paste(img, (0, 0), img)
    return contorno, mask

def montar_folha_com_contorno(lista_imgs, margin_mm, offset_mm, espaco_entre_contornos_mm):
    canvas = Image.new('RGBA', (A4_WIDTH, A4_HEIGHT), (255, 255, 255, 255))
    mask_canvas = Image.new('L', (A4_WIDTH, A4_HEIGHT), 0)
    
    margin_px = int(margin_mm * MM_TO_PX)
    offset_px = int(offset_mm * MM_TO_PX)
    spacing_px = int(espaco_entre_contornos_mm * MM_TO_PX)
    
    processed = []
    for item in lista_imgs:
        img = item['img'].convert("RGBA")
        target_w_px = int(item['width_mm'] * MM_TO_PX)
        
        # Redimensiona mantendo proporção
        w_orig, h_orig = img.size
        ratio = target_w_px / w_orig
        img_res = img.resize((target_w_px, int(h_orig * ratio)), Image.LANCZOS)
        
        # 1. Cria o contorno branco (Offset)
        img_com_borda, mask_borda = criar_contorno(img_res, offset_px)
        
        # 2. Crop para remover sobras
        bbox = img_com_borda.getbbox()
        if bbox:
            img_com_borda = img_com_borda.crop(bbox)
            mask_borda = mask_borda.crop(bbox)
            
        # 3. Máscara de colisão (engorda mais um pouco para o distanciamento entre peças)
        if spacing_px > 0:
            m_colisao = mask_borda.filter(ImageFilter.MaxFilter(spacing_px * 2 + 1))
        else:
            m_colisao = mask_borda
            
        processed.append({'img': img_com_borda, 'mask': m_colisao})

    # Maiores primeiro
    processed.sort(key=lambda x: x['img'].size[1], reverse=True)

    for p in processed:
        img, m = p['img'], p['mask']
        iw, ih = img.size
        sucesso = False
        
        # Tenta achar um vão aleatório (aumentei para 3000 tentativas)
        for _ in range(3000):
            tx = random.randint(margin_px, A4_WIDTH - iw - margin_px)
            ty = random.randint(margin_px, A4_HEIGHT - ih - margin_px)
            
            # Checa se a máscara de colisão bate em algo já colado
            pedaco_canvas = mask_canvas.crop((tx, ty, tx + iw, ty + ih))
            if not ImageChops.multiply(pedaco_canvas, m).getbbox():
                canvas.paste(img, (tx, ty), img)
                mask_canvas.paste(m, (tx, ty), m)
                sucesso = True
                break
        
        if not sucesso:
            st.warning(f"Item de {iw}px não coube. Tente aumentar as tentativas ou diminuir o offset.")

    return canvas

st.set_page_config(page_title="App Topo Pro - Com Contorno", layout="wide")
st.title("✂️ Gerador de Contorno e Encaixe Inteligente")

# --- AJUSTES NO MENU LATERAL ---
st.sidebar.header("Configurações de Corte")
offset_mm = st.sidebar.slider("Tamanho do Contorno Branco (mm)", 0.0, 10.0, 2.0, step=0.5)
espaco_mm = st.sidebar.slider("Distância entre os cortes (mm)", 0.0, 10.0, 1.0, step=0.5)
margem_folha = st.sidebar.slider("Margem da folha (mm)", 0, 30, 5)

st.sidebar.write("---")
st.sidebar.info("O app vai criar a borda branca automaticamente e encaixar as peças baseada nela.")

arquivos = st.file_uploader("Suba seus personagens (PNG)", type=['png'], accept_multiple_files=True)

if arquivos:
    config = []
    st.subheader("📏 Largura Final de cada Personagem")
    cols = st.columns(4)
    for i, arq in enumerate(arquivos):
        with cols[i % 4]:
            img = Image.open(arq)
            st.image(img, use_container_width=True)
            w = st.number_input(f"Largura (mm):", 10, 250, 80, key=f"w_{i}")
            config.append({'img': img, 'width_mm': w})

    if st.button("🚀 GERAR MONTAGEM COM CONTORNO"):
        with st.spinner('Criando bordas e procurando vãos...'):
            folha = montar_folha_com_contorno(config, margem_folha, offset_mm, espaco_mm)
            st.image(folha, use_container_width=True)
            
            pdf_buf = io.BytesIO()
            folha.convert("RGB").save(pdf_buf, format="PDF", resolution=300.0)
            st.download_button("📥 Baixar PDF para ScanNCut", pdf_buf.getvalue(), "folha_com_contorno.pdf")
