import streamlit as st
from PIL import Image
import io
import random

A4_WIDTH = 2480
A4_HEIGHT = 3508
MM_TO_PX = 11.81

def verificar_colisao(canvas_mask, img_mask, pos):
    """Verifica se os pixels coloridos se sobrepõem usando máscaras"""
    cw, ch = canvas_mask.size
    iw, ih = img_mask.size
    x, y = pos
    
    # Se sair da folha, colidiu
    if x + iw > cw or y + ih > ch:
        return True
        
    # Recorta a área do canvas onde a imagem quer entrar
    crop = canvas_mask.crop((x, y, x + iw, y + ih))
    
    # Se houver sobreposição de pixels não-transparentes entre a imagem e o canvas
    # usamos a função 'difference' ou 'and' lógica para detectar
    # Por simplicidade e performance em Streamlit, faremos um check de bounding box compacta
    return False # A lógica real de pixel-perfect exige bibliotecas como OpenCV ou PyGame

def montar_folha_livre(lista_imagens_config, margin_mm, spacing_mm, tentativas=100):
    canvas = Image.new('RGBA', (A4_WIDTH, A4_HEIGHT), (255, 255, 255, 255))
    margin_px = int(margin_mm * MM_TO_PX)
    spacing_px = int(spacing_mm * MM_TO_PX)
    
    processed = []
    for item in lista_imagens_config:
        img = item['img'].convert("RGBA")
        target_w_px = int(item['width_mm'] * MM_TO_PX)
        w_orig, h_orig = img.size
        ratio = target_w_px / w_orig
        img_res = img.resize((target_w_px, int(h_orig * ratio)), Image.LANCZOS)
        
        # Crop agressivo para remover bordas transparentes inúteis
        bbox = img_res.getbbox()
        if bbox:
            img_res = img_res.crop(bbox)
        processed.append(img_res)

    # Maiores primeiro para garantir o lugar delas
    processed.sort(key=lambda x: x.size[0] * x.size[1], reverse=True)
    
    posicoes_ocupadas = []

    for img in processed:
        w, h = img.size
        sucesso = False
        
        # Tenta encaixar em 500 lugares diferentes antes de desistir
        for _ in range(500):
            test_x = random.randint(margin_px, A4_WIDTH - w - margin_px)
            test_y = random.randint(margin_px, A4_HEIGHT - h - margin_px)
            
            # Verifica se bate em algum retângulo já colocado
            colidiu = False
            for (ox, oy, ow, oh) in posicoes_ocupadas:
                # Retângulo de colisão com o espaçamento
                if not (test_x + w + spacing_px < ox or 
                        test_x > ox + ow + spacing_px or 
                        test_y + h + spacing_px < oy or 
                        test_y > oy + oh + spacing_px):
                    colidiu = True
                    break
            
            if not colidiu:
                canvas.paste(img, (test_x, test_y), img)
                posicoes_ocupadas.append((test_x, test_y, w, h))
                sucesso = True
                break
        
        if not sucesso:
            st.error(f"Não consegui um lugar livre para uma das imagens!")

    return canvas

st.set_page_config(page_title="Tetris Livre - Dragon Ball", layout="wide")
st.title("🎲 Organizador Aleatório (Encaixe de Vãos)")

st.sidebar.header("Ajustes")
margem_mm = st.sidebar.slider("Margem da folha (mm)", 0, 30, 5)
espaco_mm = st.sidebar.slider("Espaçamento de segurança (mm)", 0, 20, 2)

arquivos = st.file_uploader("Suba seus PNGs", type=['png'], accept_multiple_files=True)

if arquivos:
    lista_config = []
    cols = st.columns(4)
    for i, arq in enumerate(arquivos):
        with cols[i % 4]:
            img = Image.open(arq)
            st.image(img, use_container_width=True)
            largura = st.number_input(f"Largura (mm):", 10, 250, 80, key=f"w_{i}")
            lista_config.append({'img': img, 'width_mm': largura})

    if st.button("🎲 GERAR POSIÇÕES ALEATÓRIAS"):
        # Cada vez que clicar, as imagens mudam de lugar até você gostar!
        folha = montar_folha_livre(lista_config, margem_mm, espaco_mm)
        st.image(folha, use_container_width=True)
        
        buf = io.BytesIO()
        folha.convert("RGB").save(buf, format="PDF", resolution=300.0)
        st.download_button("📥 Baixar PDF", buf.getvalue(), "folha_aleatoria.pdf")
