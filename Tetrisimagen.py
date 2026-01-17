import streamlit as st
from PIL import Image
import io

# Configuração da Folha A4 em 300 DPI (Padrão de alta qualidade)
A4_WIDTH = 2480
A4_HEIGHT = 3508
MM_TO_PX = 11.81  # 1mm = 11.81 pixels em 300 DPI

def montar_folha(lista_imagens_config, margin_mm, spacing_mm):
    # Cria o fundo branco da folha A4
    canvas = Image.new('RGBA', (A4_WIDTH, A4_HEIGHT), (255, 255, 255, 255))
    
    # Converte mm para pixels
    margin_px = int(margin_mm * MM_TO_PX)
    spacing_px = int(spacing_mm * MM_TO_PX)
    
    processed_images = []
    for item in lista_imagens_config:
        img = item['img']
        target_w_mm = item['width_mm']
        
        # Redimensiona a imagem conforme a largura em mm definida pelo usuário
        target_w_px = int(target_w_mm * MM_TO_PX)
        w_orig, h_orig = img.size
        ratio = target_w_px / w_orig
        new_size = (target_w_px, int(h_orig * ratio))
        img_resized = img.resize(new_size, Image.LANCZOS)
        
        # Rotação inteligente: se a imagem for muito alta, deita ela para economizar papel
        if img_resized.size[1] > img_resized.size[0] * 1.3:
            img_resized = img_resized.rotate(90, expand=True)
            
        processed_images.append(img_resized)

    # Organiza por altura (maiores primeiro) para um encaixe mais eficiente
    processed_images.sort(key=lambda x: x.size[1], reverse=True)
    
    x, y = margin_px, margin_px
    row_height = 0
    
    for img in processed_images:
        w, h = img.size
        
        # Verifica se a imagem cabe na largura da linha atual
        if x + w > A4_WIDTH - margin_px:
            x = margin_px
            y += row_height + spacing_px
            row_height = 0
            
        # Verifica se a imagem cabe na altura restante da folha
        if y + h > A4_HEIGHT - margin_px:
            st.warning("⚠️ Algumas imagens não couberam na folha. Tente diminuir o tamanho ou o espaço entre elas.")
            break
            
        # Cola a imagem respeitando a transparência (canal alpha)
        canvas.paste(img, (x, y), img)
        
        # Move o cursor X para a próxima posição somando o ESPAÇAMENTO definido
        x += w + spacing_px
        row_height = max(row_height, h)
        
    return canvas

st.set_page_config(page_title="Topo de Bolo - Ajuste em MM", layout="wide")
st.title("📏 Organizador Pro: Ajuste de Espaçamento")

# --- ÁREA DE CONFIGURAÇÃO GLOBAL ---
st.subheader("1️⃣ Configuração da Folha")
col_m, col_s = st.columns(2)

with col_m:
    margem_mm = st.number_input("Margem da borda da folha (mm)", min_value=0, max_value=50, value=5)
    st.caption("Espaço branco nas bordas da folha A4.")

with col_s:
    # AQUI ESTÁ A OPÇÃO QUE VOCÊ PEDIU:
    espaco_mm = st.number_input("Espaço entre uma imagem e outra (mm)", min_value=0, max_value=50, value=3)
    st.caption("Distância exata entre cada tag ou topo.")

st.divider()

# --- UPLOAD E CONFIGURAÇÃO INDIVIDUAL ---
st.subheader("2️⃣ Suas Imagens")
arquivos = st.file_uploader("Suba seus PNGs transparentes", type=['png'], accept_multiple_files=True)

if arquivos:
    lista_config = []
    st.write("Defina a largura de cada item separadamente:")
    
    # Exibe em colunas para facilitar a visualização no celular
    cols = st.columns(4)
    for i, arq in enumerate(arquivos):
        with cols[i % 4]:
            img = Image.open(arq)
            st.image(img, use_container_width=True)
            largura = st.number_input(f"Largura (mm):", min_value=10, max_value=250, value=60, key=f"w_{i}")
            lista_config.append({'img': img, 'width_mm': largura})
    
    st.divider()
    
    if st.button("🚀 GERAR FOLHA MONTADA"):
        with st.spinner('Organizando com o espaçamento definido...'):
            folha_final = montar_folha(lista_config, margem_mm, espaco_mm)
            
            st.image(folha_final, caption="Sua folha pronta", use_container_width=True)
            
            # Gerar PDF para download
            pdf_buffer = io.BytesIO()
            folha_final.convert("RGB").save(pdf_buffer, format="PDF", resolution=300.0)
            
            st.download_button(
                label="📥 Baixar PDF para Impressão (300 DPI)",
                data=pdf_buffer.getvalue(),
                file_name="folha_personalizada.pdf",
                mime="application/pdf"
            )
