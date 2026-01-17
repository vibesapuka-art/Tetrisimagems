import streamlit as st
from PIL import Image
import math

def layout_images(images, canvas_size=(2480, 3508), margin=40, spacing=20):
    """
    canvas_size: A4 em 300 DPI é aprox 2480x3508 pixels
    """
    canvas = Image.new('RGBA', canvas_size, (255, 255, 255, 255))
    curr_x, curr_y = margin, margin
    max_row_height = 0
    
    for img in images:
        # Redimensiona se a imagem for maior que a folha
        img.thumbnail((canvas_size[0] - 2*margin, canvas_size[1] - 2*margin))
        w, h = img.size
        
        # Verifica se precisa pular de linha
        if curr_x + w > canvas_size[0] - margin:
            curr_x = margin
            curr_y += max_row_height + spacing
            max_row_height = 0
            
        # Verifica se cabe na folha (altura)
        if curr_y + h > canvas_size[1] - margin:
            st.warning("Algumas imagens não couberam nesta folha!")
            break
            
        # Cola a imagem no canvas
        canvas.paste(img, (curr_x, curr_y), img)
        
        curr_x += w + spacing
        max_row_height = max(max_row_height, h)
        
    return canvas

st.title("🚀 Organizador de Topo de Bolo - A4")
st.write("Suba seus PNGs transparentes e eu monto a folha para você!")

uploaded_files = st.file_uploader("Escolha as artes (PNG)", accept_multiple_files=True, type=['png'])

if uploaded_files:
    images = [Image.open(file) for file in uploaded_files]
    
    # Opções de ajuste
    col1, col2 = st.columns(2)
    with col1:
        margin = st.slider("Margem da folha (segurança ScanNCut)", 0, 100, 40)
    with col2:
        spacing = st.slider("Espaço entre tags", 0, 50, 20)

    if st.button("Gerar Folha A4"):
        result_img = layout_images(images, margin=margin, spacing=spacing)
        st.image(result_img, caption="Prévia da Folha", use_column_width=True)
        
        # Converter para PDF para download
        pdf_path = "folha_impressao.pdf"
        result_img.convert("RGB").save(pdf_path, "PDF", resolution=300.0)
        
        with open(pdf_path, "rb") as f:
            st.download_button("Baixar PDF para Impressão", f, file_name="topo_de_bolo_pronto.pdf")
