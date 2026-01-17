import streamlit as st
from PIL import Image
import io

# Configuração da Folha A4 em 300 DPI (padrão de impressão)
A4_WIDTH = 2480
A4_HEIGHT = 3508

def montar_folha(images, margin, spacing, target_width_mm):
    # Converte mm para pixels (1mm aprox 11.81 pixels em 300 DPI)
    target_width_px = int(target_width_mm * 11.81)
    
    canvas = Image.new('RGBA', (A4_WIDTH, A4_HEIGHT), (255, 255, 255, 255))
    
    # Redimensiona e organiza
    processed_images = []
    for img in images:
        # Redimensiona mantendo o aspecto original
        w_orig, h_orig = img.size
        ratio = target_width_px / w_orig
        new_size = (target_width_px, int(h_orig * ratio))
        img_resized = img.resize(new_size, Image.LANCZOS)
        
        # Se a imagem for mais alta que larga, tenta girar 90º para caber melhor na linha
        if img_resized.size[1] > img_resized.size[0] * 1.5:
            img_resized = img_resized.rotate(90, expand=True)
            
        processed_images.append(img_resized)

    # Ordena da maior para a menor altura para um encaixe mais limpo
    processed_images.sort(key=lambda x: x.size[1], reverse=True)
    
    x, y = margin, margin
    row_height = 0
    
    for img in processed_images:
        w, h = img.size
        
        # Checa se precisa pular linha
        if x + w > A4_WIDTH - margin:
            x = margin
            y += row_height + spacing
            row_height = 0

        # Checa se cabe na folha atual
        if y + h > A4_HEIGHT - margin:
            st.warning("Atenção: Algumas imagens ficaram de fora. Diminua o tamanho ou use menos imagens.")
            break

        canvas.paste(img, (x, y), img)
        x += w + spacing
        row_height = max(row_height, h)
        
    return canvas

st.set_page_config(page_title="Tetris de Imagens A4", layout="wide")
st.title("🍓 Organizador de Topo de Bolo V2")

# Painel Lateral de Controles
st.sidebar.header("Configurações")
largura_tag = st.sidebar.number_input("Largura desejada da tag (em mm)", min_value=10, max_value=200, value=50)
margem = st.sidebar.slider("Margem da folha (px)", 0, 200, 60)
espaco = st.sidebar.slider("Espaço entre itens (px)", 0, 100, 30)

arquivos = st.file_uploader("Suba seus PNGs (Dragon Ball, Moranguinho, etc)", type=['png'], accept_multiple_files=True)

if arquivos:
    imgs = [Image.open(arq) for arq in arquivos]
    
    if st.button("Gerar Montagem"):
        with st.spinner('Organizando peças...'):
            folha_pronta = montar_folha(imgs, margem, espaco, largura_tag)
            
            st.image(folha_pronta, caption="Prévia para Impressão", use_container_width=True)
            
            # Gerar PDF
            pdf_buffer = io.BytesIO()
            folha_pronta.convert("RGB").save(pdf_buffer, format="PDF", resolution=300.0)
            
            st.download_button(
                label="📥 Baixar PDF Pronto",
                data=pdf_buffer.getvalue(),
                file_name="topo_organizado.pdf",
                mime="application/pdf"
            )
