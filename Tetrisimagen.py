import streamlit as st
from PIL import Image, ImageChops, ImageFilter, ImageDraw, ImageOps
import io
import random

# Configuração da Folha A4 em 300 DPI
A4_WIDTH = 2480
A4_HEIGHT = 3508
MM_TO_PX = 11.81

def gerar_contorno_perfeito(img, sangria_mm, espessura_linha):
    """Gera uma silhueta sólida, sem furos internos e com curvas arredondadas"""
    sangria_px = int(sangria_mm * MM_TO_PX)
    
    # 1. Criar máscara binária da imagem (remove transparências parciais)
    alpha = img.split()[3].point(lambda p: 255 if p > 50 else 0)
    
    # 2. FECHAR BURACOS INTERNOS (Inundação/Flood Fill)
    # Criamos uma versão maior da máscara para garantir que o fundo seja detectado corretamente
    mask_temp = alpha.filter(ImageFilter.MaxFilter(3))
    bg = Image.new("L", (mask_temp.width + 2, mask_temp.height + 2), 0)
    bg.paste(mask_temp, (1, 1))
    # Preenche o fundo externo com branco
    ImageDraw.floodfill(bg, (0, 0), 255)
    # Inverte para que apenas o corpo do personagem (incluindo buracos internos) fique branco
    mask_solida = ImageOps.invert(bg.crop((1, 1, mask_temp.width + 1, mask_temp.height + 1)))
    # Garante que a máscara original esteja inclusa
    mask_corpo = ImageChops.lighter(alpha, mask_solida)

    # 3. CRIAR A SANGRIA BRANCA SUAVE (Arredondamento)
    # Expandimos a máscara sólida para o tamanho da sangria
    mask_sangria = mask_corpo.filter(ImageFilter.MaxFilter(sangria_px * 2 + 1))
    # Suavização Gaussiana pesada para arredondar 'colinas' e pontas
    mask_sangria = mask_sangria.filter(ImageFilter.GaussianBlur(radius=6))
    # Binarização para deixar a borda nítida para o scanner
    mask_sangria = mask_sangria.point(lambda p: 255 if p > 120 else 0)

    # 4. CRIAR A LINHA PRETA EXTERNA
    mask_linha = mask_sangria.filter(ImageFilter.MaxFilter(espessura_linha * 2 + 1))
    
    # Montagem final da peça
    peca_final = Image.new("RGBA", img.size, (0, 0, 0, 0))
    preto = Image.new("RGBA", img.size, (0, 0, 0, 255))
    branco = Image.new("RGBA", img.size, (255, 255, 255, 255))
    
    # Ordem das camadas: Linha Preta -> Fundo Branco Sólido -> Desenho
    peca_final.paste(preto, (0, 0), mask_linha)
    peca_final.paste(branco, (0, 0), mask_sangria)
    peca_final.paste(img, (0, 0), img)
    
    return peca_final, mask_linha

def montar_folha_scanncut(lista_config, margem_mm, sangria_mm, espaco_mm, linha_px):
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
        
        # Crop para remover sobras de transparência
        bbox = img_res.getbbox()
        if bbox: img_res = img_res.crop(bbox)
            
        img_contornada, mask_colisao = gerar_contorno_perfeito(img_res, sangria_mm, linha_px)
        
        # Máscara de colisão com folga extra para o 'Tetris'
        if espaco_px > 0:
            m_c = mask_colisao.filter(ImageFilter.MaxFilter(espaco_px * 2 + 1))
        else:
            m_c = mask_colisao
            
        processed.append({'img': img_contornada, 'mask': m_c})

    # Maiores primeiro para otimizar os vãos
    processed.sort(key=lambda x: x['img'].size[1], reverse=True)

    for p in processed:
        img, m = p['img'], p['mask']
        iw, ih = img.size
        sucesso = False
        for _ in range(5000): # Alta insistência para encaixe aleatório
            tx = random.randint(margem_px, A4_WIDTH - iw - margem_px)
            ty = random.randint(margem_px, A4_HEIGHT - ih - margem_px)
            
            check_area = mask_canvas.crop((tx, ty, tx + iw, ty + ih))
            if not ImageChops.multiply(check_area, m).getbbox():
                canvas.paste(img, (tx, ty), img)
                mask_canvas.paste(m, (tx, ty), m)
                sucesso = True
                break
    return canvas

# --- INTERFACE ---
st.set_page_config(page_title="ScanNCut Final Pro", layout="wide")
st.title("🎯 ScanNCut: Contorno Sólido e Curvas Lisas")

st.sidebar.header("Configurações de Corte")
sangria_val = st.sidebar.number_input("Tamanho da Sangria Branca (mm)", 1.0, 10.0, 3.0, 0.5)
espaco_val = st.sidebar.number_input("Distância entre Peças (mm)", 0.0, 10.0, 1.0, 0.5)
linha_val = st.sidebar.slider("Espessura da Linha do Scanner (px)", 1, 5, 2)
margem_val = st.sidebar.slider("Margem da Folha (mm)", 5, 30, 10)

arquivos = st.file_uploader("Upload PNGs", type=['png'], accept_multiple_files=True)

if arquivos:
    config_list = []
    cols = st.columns(4)
    for i, arq in enumerate(arquivos):
        with cols[i % 4]:
            img = Image.open(arq)
            st.image(img, use_container_width=True)
            w_mm = st.number_input(f"Largura (mm):", 10, 250, 80, key=f"w_{i}")
            config_list.append({'img': img, 'width_mm': w_mm})

    if st.button("🚀 GERAR FOLHA PROFISSIONAL"):
        with st.spinner('Processando silhuetas e fechando buracos...'):
            folha = montar_folha_scanncut(config_list, margem_val, sangria_val, espaco_val, linha_val)
            st.image(folha, use_container_width=True)
            
            buf = io.BytesIO()
            folha.convert("RGB").save(buf, format="PDF", resolution=300.0)
            st.download_button("📥 Baixar PDF", buf.getvalue(), "folha_scanncut_perfeita.pdf")
