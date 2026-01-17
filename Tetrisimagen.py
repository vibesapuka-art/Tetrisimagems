import streamlit as st
from PIL import Image, ImageChops, ImageFilter, ImageOps
import io
import random

# Configuração A4 300 DPI
A4_WIDTH = 2480
A4_HEIGHT = 3508
MM_TO_PX = 11.81

def gerar_contorno_scanncut(img, sangria_mm):
    """Cria a sangria branca e uma linha preta fina para o scanner ler"""
    sangria_px = int(sangria_mm * MM_TO_PX)
    alpha = img.split()[3]
    
    # 1. Cria a máscara da sangria (espaço branco)
    mask_sangria = alpha.filter(ImageFilter.MaxFilter(sangria_px * 2 + 1))
    
    # 2. Cria a linha preta (um tiquinho maior que a sangria)
    # A linha preta terá 1px de espessura para o scanner ler
    mask_linha = mask_sangria.filter(ImageFilter.MaxFilter(3)) 
    
    # Criar a imagem final
    nova_img = Image.new("RGBA", img.size, (0, 0, 0, 0))
    
    # Pinta o contorno de preto
    preto = Image.new("RGBA", img.size, (0, 0, 0, 255))
    nova_img.paste(preto, (0, 0), mask_linha)
    
    # Pinta a sangria de branco por cima (deixando só a bordinha preta)
    branco = Image.new("RGBA", img.size, (255, 255, 255, 255))
    nova_img.paste(branco, (0, 0), mask_sangria)
    
    # Cola a imagem original no centro
    nova_img.paste(img, (0, 0), img)
    
    return nova_img, mask_linha

def montar_folha_final(lista_config, margem_mm, sangria_mm, espaco_mm):
    canvas = Image.new('RGBA', (A4_WIDTH, A4_HEIGHT), (255, 255, 255, 255))
    mask_canvas = Image.new('L', (A4_WIDTH, A4_HEIGHT), 0)
    
    margem_px = int(margem_mm * MM_TO_PX)
    espaco_px = int(espaco_mm * MM_TO_PX)
    
    processed = []
    for item in lista_config:
        img_orig = item['img'].convert("RGBA")
        w_px = int(item['width_mm'] * MM_TO_PX)
        ratio = w_px / img_orig.size[0]
        img_res = img_orig.resize((w_px, int(img_orig.size[1] * ratio)), Image.LANCZOS)
        
        bbox = img_res.getbbox()
        if bbox: img_res = img_res.crop(bbox)
            
        # Gera a imagem com a sangria branca e o contorno preto
        img_final, mask_colisao = gerar_contorno_scanncut(img_res, sangria_mm)
        
        # Adiciona folga extra para colisão se definido
        if espaco_px > 0:
            m_colisao = mask_colisao.filter(ImageFilter.MaxFilter(espaco_px * 2 + 1))
        else:
            m_colisao = mask_colisao
            
        processed.append({'img': img_final, 'mask': m_colisao})

    processed.sort(key=lambda x: x['img'].size[1], reverse=True)

    for p in processed:
        img, m = p['img'], p['mask']
        iw, ih = img.size
        sucesso = False
        
        for _ in range(5000): # Alta insistência para encaixar nos vãos
            tx = random.randint(margem_px, A4_WIDTH - iw - margem_px)
            ty = random.randint(margem_px, A4_HEIGHT - ih - margin_px)
            
            pedaco = mask_canvas.crop((tx, ty, tx + iw, ty + ih))
            if not ImageChops.multiply(pedaco, m).getbbox():
                canvas.paste(img, (tx, ty), img)
                mask_canvas.paste(m, (tx, ty), m)
                sucesso = True
                break
        
        if not sucesso:
            st.warning(f"Não coube uma das imagens. Tente reduzir a sangria ou o espaço.")

    return canvas

st.set_page_config(page_title="ScanNCut Precision", layout="wide")
st.title("🎯 ScanNCut: Contorno Preto + Sangria")

st.sidebar.header("Ajustes de Corte")
sangria_mm = st.sidebar.number_input("Tamanho da Sangria Branca (mm)", 0.5, 10.0, 2.0, 0.5)
espaco_mm = st.sidebar.number_input("Distância entre as Linhas Pretas (mm)", 0.0, 10.0, 1.0, 0.5)
margem_folha = st.sidebar.slider("Margem da Folha (mm)", 5, 30, 10)

st.sidebar.info("💡 A linha preta é para o scanner. Configure o 'Corte Negativo' na sua máquina para cortar dentro desta linha.")

arquivos = st.file_uploader("Suba seus PNGs", type=['png'], accept_multiple_files=True)

if arquivos:
    config = []
    cols = st.columns(4)
    for i, arq in enumerate(arquivos):
        with cols[i % 4]:
            img = Image.open(arq)
            st.image(img, use_container_width=True)
            w = st.number_input(f"Largura (mm):", 10, 250, 70, key=f"w_{i}")
            config.append({'img': img, 'width_mm': w})

    if st.button("🚀 GERAR FOLHA COM CONTORNO PRETO"):
        with st.spinner('Desenhando contornos e encaixando...'):
            folha = montar_folha_final(config, margem_folha, sangria_mm, espaco_mm)
            st.image(folha, use_container_width=True)
            
            pdf_buf = io.BytesIO()
            folha.convert("RGB").save(pdf_buf, format="PDF", resolution=300.0)
            st.download_button("📥 Baixar PDF para Impressão", pdf_buf.getvalue(), "folha_corte_direto.pdf")
