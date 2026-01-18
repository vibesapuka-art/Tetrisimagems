import streamlit as st
from PIL import Image, ImageChops, ImageFilter, ImageDraw, ImageOps
import io
import random

# Configuração A4 300 DPI
A4_WIDTH = 2480
A4_HEIGHT = 3508
CM_TO_PX = 118.11 

def gerar_contorno_fast(img, sangria_cm, suavidade, linha_ativa):
    respiro = int(sangria_cm * CM_TO_PX * 2) + 60 
    img_exp = Image.new("RGBA", (img.width + respiro, img.height + respiro), (0, 0, 0, 0))
    img_exp.paste(img, (respiro // 2, respiro // 2))
    
    alpha = img_exp.split()[3].point(lambda p: 255 if p > 100 else 0)
    
    # Suavidade simplificada para rapidez
    n_blur = 8 if suavidade == "Média" else (20 if suavidade == "Alta" else 2)
    n_max = 25 if suavidade == "Média" else (65 if suavidade == "Alta" else 5)

    mask = alpha.filter(ImageFilter.MaxFilter(int(n_max)))
    # Processo de bolha rápido
    sangria_px = int(sangria_cm * CM_TO_PX)
    if sangria_px > 0:
        mask = mask.filter(ImageFilter.MaxFilter(int(sangria_px)))
    mask = mask.filter(ImageFilter.GaussianBlur(n_blur)).point(lambda p: 255 if p > 128 else 0)

    nova_img = Image.new("RGBA", img_exp.size, (0, 0, 0, 0))
    if linha_ativa:
        linha_mask = mask.filter(ImageFilter.MaxFilter(3))
        nova_img.paste((0,0,0,255), (0,0), linha_mask)
    
    nova_img.paste((255,255,255,255), (0,0), mask)
    nova_img.paste(img_exp, (0,0), img_exp)
    return nova_img.crop(nova_img.getbbox()), mask.crop(nova_img.getbbox())

def montar_folha_png_only(lista_config, margem_cm, sangria_cm, espaco_cm, suavidade, linha_ativa, modo_layout, permitir_90):
    canvas = Image.new('RGBA', (A4_WIDTH, A4_HEIGHT), (255, 255, 255, 255))
    mask_canvas = Image.new('L', (A4_WIDTH, A4_HEIGHT), 0)
    m_px = int(margem_cm * CM_TO_PX)
    e_px = int(espaco_cm * CM_TO_PX)
    
    all_pieces = []
    for item in lista_config:
        img = item['img'].convert("RGBA")
        if item['espelhar']: img = ImageOps.mirror(img)
        w_px = int(item['width_cm'] * CM_TO_PX)
        img = img.resize((w_px, int(img.size[1] * (w_px/img.size[0]))), Image.Resampling.LANCZOS)
        
        peca, m_c = gerar_contorno_fast(img, sangria_cm, suavidade, linha_ativa)
        p_90, m_90 = (peca.rotate(90, expand=True), m_c.rotate(90, expand=True)) if permitir_90 else (None, None)

        for _ in range(item['quantidade']):
            all_pieces.append({'orig': (peca, m_c), 'rot': (p_90, m_90)})

    all_pieces.sort(key=lambda x: x['orig'][0].size[1], reverse=True)
    sucesso = 0

    for p in all_pieces:
        encaixou = False
        opcoes = [p['orig']]
        if p['rot'][0]: opcoes.append(p['rot'])
        
        for img_p, mask_p in opcoes:
            iw, ih = img_p.size
            # Reduzi para 800 tentativas para ser MUITO mais rápido
            for _ in range(800):
                tx, ty = random.randint(m_px, A4_WIDTH-iw-m_px), random.randint(m_px, A4_HEIGHT-ih-m_px)
                if not ImageChops.multiply(mask_canvas.crop((tx, ty, tx+iw, ty+ih)), mask_p).getbbox():
                    canvas.paste(img_p, (tx, ty), img_p)
                    mask_canvas.paste(mask_p, (tx, ty), mask_p)
                    encaixou = sucesso = sucesso + 1
                    break
            if encaixou: break
    return canvas, sucesso

# Interface Simplificada para PNG
st.set_page_config(page_title="Fast ScanNCut PNG", layout="wide")
st.title("⚡ Gerador Ultra Rápido (Somente PNG)")

uploads = st.file_uploader("PNGs", type=['png'], accept_multiple_files=True)
if uploads:
    config_list = []
    cols = st.columns(5)
    for i, arq in enumerate(uploads):
        with cols[i % 5]:
            img = Image.open(arq)
            st.image(img, width=80)
            l = st.number_input(f"cm", 1.0, 20.0, 7.0, 0.1, key=f"w{i}")
            q = st.number_input(f"qtd", 1, 50, 1, key=f"q{i}")
            config_list.append({'img': img, 'width_cm': l, 'quantidade': q, 'espelhar': st.checkbox("Mirror", key=f"m{i}")})

    if st.button("🚀 GERAR PNG"):
        with st.spinner("Processando..."):
            folha, count = montar_folha_png_only(config_list, 1.0, 0.4, 0.2, "Alta", True, "Tetris", True)
            st.image(folha)
            buf = io.BytesIO()
            folha.save(buf, format="PNG")
            st.download_button("📥 Baixar PNG Final", buf.getvalue(), "folha_fast.png", use_container_width=True)
