import streamlit as st
from PIL import Image, ImageChops
import io
import random

A4_WIDTH = 2480
A4_HEIGHT = 3508
MM_TO_PX = 11.81

def verificar_colisao_real(canvas_mask, img_mask, pos):
    """Verifica se os pixels coloridos realmente se tocam"""
    x, y = pos
    # Cria uma área temporária para teste
    test_area = canvas_mask.crop((x, y, x + img_mask.size[0], y + img_mask.size[1]))
    # Multiplica as máscaras: se houver qualquer pixel comum, o resultado não será zero
    overlap = ImageChops.multiply(test_area, img_mask)
    if overlap.getbbox(): # Se houver algo além de transparente, colidiu
        return True
    return False

def montar_folha_pixel_perfect(lista_imagens_config, margin_mm, spacing_mm):
    # Canvas principal e máscara de ocupação (começa toda preta/vazia)
    canvas = Image.new('RGBA', (A4_WIDTH, A4_HEIGHT), (255, 255, 255, 255))
    mask_canvas = Image.new('L', (A4_WIDTH, A4_HEIGHT), 0) 
    
    margin_px = int(margin_mm * MM_TO_PX)
    spacing_px = int(spacing_mm * MM_TO_PX)
    
    processed = []
    for item in lista_imagens_config:
        img = item['img'].convert("RGBA")
        target_w_px = int(item['width_mm'] * MM_TO_PX)
        w_orig, h_orig = img.size
        ratio = target_w_px / w_orig
        img_res = img.resize((target_w_px, int(h_orig * ratio)), Image.LANCZOS)
        
        # Crop para garantir que não há borda vazia sobrando
        bbox = img_res.getbbox()
        if bbox: img_res = img_res.crop(bbox)
        
        # Gera a máscara da parte colorida (onde tem cor vira branco na máscara)
        img_mask = img_res.split()[3].point(lambda p: 255 if p > 50 else 0)
        # Expande um pouco a máscara para dar o 'spacing' (espaço de segurança)
        if spacing_px > 0:
            from PIL import ImageFilter
            img_mask = img_mask.filter(ImageFilter.MaxFilter(spacing_px))
            
        processed.append({'img': img_res, 'mask': img_mask})

    # Ordena: maiores primeiro
    processed.sort(key=lambda x: x['img'].size[1], reverse=True)

    for p in processed:
        img, img_mask = p['img'], p['mask']
        w, h = img.size
        sucesso = False
        
        # Varredura inteligente: busca o primeiro buraco de cima para baixo
        for y in range(margin_px, A4_HEIGHT - h - margin_px, 15): # pula de 15 em 15 px para ser rápido
            for x in range(margin_px, A4_WIDTH - w - margin_px, 15):
                if not verificar_colisao_real(mask_canvas, img_mask, (x, y)):
                    canvas.paste(img, (x, y), img)
                    mask_canvas.paste(img_mask, (x, y), img_mask)
                    sucesso = True
                    break
            if sucesso: break
            
        if not sucesso:
            st.warning(f"Não coube tudo! Tente diminuir o tamanho de algum item.")

    return canvas

st.set_page_config(page_title="App Papelaria Inteligente", layout="wide")
st.title("🍓 Encaixe Real de Topo de Bolo")

st.sidebar.header("Ajustes de Precisão")
margem_mm = st.sidebar.number_input("Margem Folha (mm)", 0, 30, 5)
espaco_mm = st.sidebar.number_input("Folga entre Cortes (mm)", 0, 10, 2)

arquivos = st.file_uploader("Suba seus PNGs", type=['png'], accept_multiple_files=True)

if arquivos:
    lista_config = []
    cols = st.columns(4)
    for i, arq in enumerate(arquivos):
        with cols[i % 4]:
            img = Image.open(arq)
            st.image(img, use_container_width=True)
            largura = st.number_input(f"Largura (mm): {arq.name[:8]}", 10, 250, 80, key=f"w_{i}")
            lista_config.append({'img': img, 'width_mm': largura})

    if st.button("🚀 GERAR MONTAGEM TIGHT (ENCAIXADA)"):
        with st.spinner('Analisando contornos e encaixando...'):
            folha = montar_folha_pixel_perfect(lista_config, margem_mm, espaco_mm)
            st.image(folha, use_container_width=True)
            
            buf = io.BytesIO()
            folha.convert("RGB").save(buf, format="PDF", resolution=300.0)
            st.download_button("📥 Baixar PDF", buf.getvalue(), "folha_perfeita.pdf")
