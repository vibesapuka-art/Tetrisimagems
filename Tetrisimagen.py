import streamlit as st
from PIL import Image
import io

# Configuração da Folha A4 em 300 DPI
A4_WIDTH = 2480
A4_HEIGHT = 3508

def montar_folha(images, margin, spacing):
    # Cria o fundo branco
    canvas = Image.new('RGBA', (A4_WIDTH, A4_HEIGHT), (255, 255, 255, 255))
    
    # Ordena imagens da maior para a menor (melhora o encaixe)
    images.sort(key=lambda x: x.size[1], reverse=True)
    
    x, y = margin, margin
    row_height = 0
    
    for img in images:
        w, h = img.size
        
        # Se a imagem for maior que a largura da folha, redimensiona
        if w > (A4_WIDTH - 2*margin):
            ratio = (A4_WIDTH - 2*margin) / w
            img = img.resize((int(w*ratio), int(h*ratio)), Image.LANCZOS)
            w, h = img.size

        # Verifica se precisa ir para a próxima linha
        if x + w > A4_WIDTH - margin:
            x = margin
            y += row_height + spacing
            row_height = 0

        # Se ultrapassar a altura da folha, para de adicionar
        if y + h > A4_HEIGHT - margin:
            st.error("Ops! Nem tudo coube em uma folha só.")
            break

        # Cola a imagem (usa o próprio canal alpha como máscara para transparência)
        canvas.paste(img, (x, y), img)
        
        x += w + spacing
        row_height = max(row_height, h)
        
    return canvas

st.set_page_config(page_title="Tetris de Imagens A4", layout="wide")
st.title("🍓 Organizador de Topo de Bolo (ScanNCut)")

# Upload
arquivos = st.file_uploader("Suba seus PNGs transparentes aqui", type=['png'], accept_multiple_files=True)

if arquivos:
    # Sliders para você ajustar ao vivo
    margem = st.sidebar.slider("Margem da folha (px)", 0, 200, 50)
    espaco = st.sidebar.slider("Espaço entre itens (px)", 0, 100, 20)
    
    imgs = [Image.open(arq) for arq in arquivos]
    
    if st.button("Gerar Montagem Automática"):
        folha_pronta = montar_folha(imgs, margem, espaco)
        
        # Exibe na tela
        st.image(folha_pronta, caption="Sua folha organizada", use_container_width=True)
        
        # Prepara o PDF
        pdf_buffer = io.BytesIO()
        folha_pronta.convert("RGB").save(pdf_buffer, format="PDF", resolution=300.0)
        
        st.download_button(
            label="📥 Baixar PDF para Impressão",
            data=pdf_buffer.getvalue(),
            file_name="folha_pronta_impressao.pdf",
            mime="application/pdf"
        )
