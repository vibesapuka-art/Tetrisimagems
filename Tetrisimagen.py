import streamlit as st
from PIL import Image
import io

# Configuração da Folha A4 em 300 DPI
A4_WIDTH = 2480
A4_HEIGHT = 3508
MM_TO_PX = 11.81  # Conversão aproximada para 300 DPI

def montar_folha(lista_imagens_config, margin, spacing):
    canvas = Image.new('RGBA', (A4_WIDTH, A4_HEIGHT), (255, 255, 255, 255))
    
    processed_images = []
    for item in lista_imagens_config:
        img = item['img']
        target_w_mm = item['width_mm']
        
        # Redimensiona a imagem individualmente
        target_w_px = int(target_w_mm * MM_TO_PX)
        w_orig, h_orig = img.size
        ratio = target_w_px / w_orig
        new_size = (target_w_px, int(h_orig * ratio))
        img_resized = img.resize(new_size, Image.LANCZOS)
        
        # Rotação automática para economia de espaço
        if img_resized.size[1] > img_resized.size[0] * 1.2:
            img_resized = img_resized.rotate(90, expand=True)
            
        processed_images.append(img_resized)

    # Ordena para melhor encaixe
    processed_images.sort(key=lambda x: x.size[1], reverse=True)
    
    x, y = margin, margin
    row_height = 0
    
    for img in processed_images:
        w, h = img.size
        if x + w > A4_WIDTH - margin:
            x = margin
            y += row_height + spacing
            row_height = 0
        if y + h > A4_HEIGHT - margin:
            st.warning("Algumas imagens não couberam!")
            break
        canvas.paste(img, (x, y), img)
        x += w + spacing
        row_height = max(row_height, h)
        
    return canvas

st.set_page_config(page_title="Organizador Pro - Topo de Bolo", layout="wide")
st.title("🎨 Organizador Personalizado (Tamanhos Individuais)")

st.sidebar.header("Ajustes da Folha")
margem = st.sidebar.slider("Margem da folha (px)", 0, 200, 60)
espaco = st.sidebar.slider("Espaço entre itens (px)", 0, 100, 30)

arquivos = st.file_uploader("Suba seus PNGs", type=['png'], accept_multiple_files=True)

if arquivos:
    lista_config = []
    st.subheader("Configurar Tamanhos (Largura em mm)")
    
    # Cria colunas para organizar os campos de entrada de tamanho
    cols = st.columns(3)
    for i, arq in enumerate(arquivos):
        with cols[i % 3]:
            img = Image.open(arq)
            st.image(img, width=100)
            # Campo de entrada para cada imagem
            largura = st.number_input(f"Largura {arq.name}", min_value=10, max_value=200, value=50, key=f"w_{i}")
            lista_config.append({'img': img, 'width_mm': largura})
    
    if st.button("🚀 Gerar Montagem Perfeita"):
        with st.spinner('Calculando melhor encaixe...'):
            folha = montar_folha(lista_config, margem, espaco)
            st.image(folha, caption="Folha Finalizada", use_container_width=True)
            
            pdf_buffer = io.BytesIO()
            folha.convert("RGB").save(pdf_buffer, format="PDF", resolution=300.0)
            st.download_button("📥 Baixar PDF", data=pdf_buffer.getvalue(), file_name="topo_custom.pdf")
