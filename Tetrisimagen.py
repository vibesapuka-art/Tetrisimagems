import streamlit as st
from PIL import Image
import io

# Configuração da Folha A4 em 300 DPI
A4_WIDTH = 2480
A4_HEIGHT = 3508
MM_TO_PX = 11.81

def montar_folha_compacta(lista_imagens_config, margin_mm, spacing_mm):
    # Fundo branco
    canvas = Image.new('RGBA', (A4_WIDTH, A4_HEIGHT), (255, 255, 255, 255))
    
    margin_px = int(margin_mm * MM_TO_PX)
    spacing_px = int(spacing_mm * MM_TO_PX)
    
    # Prepara e redimensiona as imagens
    processed = []
    for item in lista_imagens_config:
        img = item['img'].convert("RGBA")
        target_w_px = int(item['width_mm'] * MM_TO_PX)
        
        # Redimensionamento
        w_orig, h_orig = img.size
        ratio = target_w_px / w_orig
        img_res = img.resize((target_w_px, int(h_orig * ratio)), Image.LANCZOS)
        
        # Crop automático para remover excesso de transparência em volta
        bbox = img_res.getbbox()
        if bbox:
            img_res = img_res.crop(bbox)
            
        processed.append(img_res)

    # Ordenar por altura para facilitar o encaixe lateral
    processed.sort(key=lambda x: x.size[1], reverse=True)

    x, y = margin_px, margin_px
    row_height = 0
    
    # Lista para guardar as posições e evitar sobreposição real (futura implementação de máscara)
    for img in processed:
        w, h = img.size

        # Se não couber na largura, pula linha
        if x + w > A4_WIDTH - margin_px:
            x = margin_px
            y += row_height + spacing_px
            row_height = 0

        # Se não couber na altura, para
        if y + h > A4_HEIGHT - margin_px:
            st.warning("⚠️ Algumas imagens ficaram de fora!")
            break

        # AQUI ESTÁ O SEGREDO: 
        # Tenta "espremer" a imagem para a esquerda verificando o conteúdo
        # Por enquanto, reduzimos o 'bounding box' para o limite do pixel colorido
        canvas.paste(img, (x, y), img)
        
        # O próximo X agora é calculado com base no final da imagem + seu espaçamento personalizado
        x += w + spacing_px
        row_height = max(row_height, h)
        
    return canvas

st.set_page_config(page_title="Tetris Real - Topo de Bolo", layout="wide")
st.title("🧩 Organizador de Encaixe Inteligente")

st.subheader("1️⃣ Ajuste Geral")
c1, c2 = st.columns(2)
with c1:
    margem_mm = st.number_input("Margem da folha (mm)", 0, 50, 5)
with c2:
    # Reduzindo esse valor, as imagens vão se "atropelar" visualmente, 
    # mas como são transparentes, o scanner lerá os contornos certos!
    espaco_mm = st.number_input("Espaço entre contornos (mm)", -20, 50, 2) 
    st.info("💡 Use valores baixos ou até negativos para 'encaixar' cabelos e braços nos vãos.")

st.divider()

arquivos = st.file_uploader("Suba seus PNGs do Dragon Ball", type=['png'], accept_multiple_files=True)

if arquivos:
    lista_config = []
    st.subheader("2️⃣ Definir Tamanhos Individuais")
    cols = st.columns(4)
    for i, arq in enumerate(arquivos):
        with cols[i % 4]:
            img = Image.open(arq)
            st.image(img, use_container_width=True)
            largura = st.number_input(f"Largura (mm): {arq.name[:10]}", 10, 250, 70, key=f"w_{i}")
            lista_config.append({'img': img, 'width_mm': largura})

    if st.button("🚀 GERAR ENCAIXE"):
        folha = montar_folha_compacta(lista_config, margem_mm, espaco_mm)
        st.image(folha, use_container_width=True)
        
        buf = io.BytesIO()
        folha.convert("RGB").save(buf, format="PDF", resolution=300.0)
        st.download_button("📥 Baixar PDF", buf.getvalue(), "folha_tetris.pdf")
