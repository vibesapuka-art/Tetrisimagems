import streamlit as st
from PIL import Image
import io

# Configuração da Folha A4 em 300 DPI
A4_WIDTH = 2480
A4_HEIGHT = 3508
MM_TO_PX = 11.81  # Fator de conversão (1mm = 11.81 pixels em 300 DPI)

def montar_folha(lista_imagens_config, margin_mm, spacing_mm):
    canvas = Image.new('RGBA', (A4_WIDTH, A4_HEIGHT), (255, 255, 255, 255))
    
    # Converte milímetros da interface para pixels do processamento
    margin_px = int(margin_mm * MM_TO_PX)
    spacing_px = int(spacing_mm * MM_TO_PX)
    
    processed_images = []
    for item in lista_imagens_config:
        img = item['img']
        target_w_mm = item['width_mm']
        
        # Redimensiona a imagem com base no mm escolhido
        target_w_px = int(target_w_mm * MM_TO_PX)
        w_orig, h_orig = img.size
        ratio = target_w_px / w_orig
        new_size = (target_w_px, int(h_orig * ratio))
        img_resized = img.resize(new_size, Image.LANCZOS)
        
        # Rotação automática: se for muito alta, "deita" a imagem para economizar linha
        if img_resized.size[1] > img_resized.size[0] * 1.2:
            img_resized = img_resized.rotate(90, expand=True)
            
        processed_images.append(img_resized)

    # Organiza por altura (maiores primeiro) para otimizar o espaço
    processed_images.sort(key=lambda x: x.size[1], reverse=True)
    
    x, y = margin_px, margin_px
    row_height = 0
    
    for img in processed_images:
        w, h = img.size
        
        # Verifica se precisa pular de linha
        if x + w > A4_WIDTH - margin_px:
            x = margin_px
            y += row_height + spacing_px
            row_height = 0
            
        # Verifica se cabe na folha
        if y + h > A4_HEIGHT - margin_px:
            st.warning("O papel acabou! Algumas imagens não couberam nesta folha.")
            break
            
        canvas.paste(img, (x, y), img)
        x += w + spacing_px
        row_height = max(row_height, h)
        
    return canvas

st.set_page_config(page_title="Topo de Bolo Pro - Ajuste em MM", layout="wide")
st.title("✂️ Organizador de Papelaria (Ajuste em Milímetros)")

# Menu Lateral
st.sidebar.header("Configurações da Folha (mm)")
margem_mm = st.sidebar.number_input("Margem da Folha (mm)", min_value=0, max_value=50, value=5)
espaco_mm = st.sidebar.number_input("Espaço entre Imagens (mm)", min_value=0, max_value=50, value=3)

st.sidebar.info("💡 Dica: Para a ScanNCut, use pelo menos 3mm de espaço para o scanner não se confundir.")

arquivos = st.file_uploader("Suba seus arquivos PNG", type=['png'], accept_multiple_files=True)

if arquivos:
    lista_config = []
    st.subheader("📏 Defina a largura de cada peça")
    
    cols = st.columns(4) # Exibe em 4 colunas para caber mais na tela do celular/PC
    for i, arq in enumerate(arquivos):
        with cols[i % 4]:
            img = Image.open(arq)
            st.image(img, use_container_width=True)
            largura = st.number_input(f"Largura (mm): {arq.name[:10]}...", min_value=10, max_value=200, value=50, key=f"w_{i}")
            lista_config.append({'img': img, 'width_mm': largura})
    
    if st.button("✨ Gerar Folha para Impressão"):
        with st.spinner('Encaixando peças...'):
            folha = montar_folha(lista_config, margem_mm, espaco_mm)
            st.image(folha, caption="Sua folha organizada", use_container_width=True)
            
            # Preparação do arquivo final
            pdf_buffer = io.BytesIO()
            folha.convert("RGB").save(pdf_buffer, format="PDF", resolution=300.0)
            
            st.download_button(
                label="📥 Baixar PDF Pronto (300 DPI)",
                data=pdf_buffer.getvalue(),
                file_name="folha_montada_mm.pdf",
                mime="application/pdf"
            )
