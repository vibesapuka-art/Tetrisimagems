import streamlit as st
from PIL import Image, ImageChops, ImageFilter, ImageOps
import io
import random

# Configuração A4 300 DPI
A4_WIDTH = 2480
A4_HEIGHT = 3508
CM_TO_PX = 118.11 

def tornar_impar(n):
    n = int(n)
    return n if n % 2 != 0 else n + 1

def gerar_contorno_individual(img, sangria_cm, linha_ativa):
    # Se a sangria for 0, retorna a imagem original com máscara justa
    if sangria_cm <= 0:
        alpha = img.split()[3].point(lambda p: 255 if p > 100 else 0)
        return img, alpha

    p_px = int(sangria_cm * CM_TO_PX)
    respiro = p_px * 2 + 60
    img_exp = Image.new("RGBA", (img.width + respiro, img.height + respiro), (0, 0, 0, 0))
    img_exp.paste(img, (respiro // 2, respiro // 2))
    
    alpha = img_exp.split()[3].point(lambda p: 255 if p > 100 else 0)
    
    # Criar a bolha de sangria
    mask_corte = alpha.filter(ImageFilter.MaxFilter(tornar_impar(p_px + 15)))
    mask_corte = mask_corte.filter(ImageFilter.GaussianBlur(3)).point(lambda p: 255 if p > 128 else 0)

    # Imagem Visual
    nova_img = Image.new("RGBA", img_exp.size, (0, 0, 0, 0))
    if linha_ativa:
        # Borda preta externa
        borda_ext = mask_corte.filter(ImageFilter.MaxFilter(5))
        nova_img.paste((0,0,0,255), (0,0), borda_ext)
    
    nova_img.paste((255,255,255,255), (0,0), mask_corte)
    nova_img.paste(img_exp, (0,0), img_exp)
    
    bbox = nova_img.getbbox()
    if bbox:
        mask_colisao = mask_corte.filter(ImageFilter.MaxFilter(3)).crop(bbox)
        return nova_img.crop(bbox), mask_colisao
    return nova_img, mask_corte

def montar_projeto(lista_config, margem_cm):
    m_px = int(margem_cm * CM_TO_PX)
    e_px = int(0.15 * CM_TO_PX)
    all_pieces = []
    
    # 1. Preparar cada imagem com sua configuração própria
    for item in lista_config:
        img = item['img'].convert("RGBA")
        if item['espelhar']: img = ImageOps.mirror(img)
        
        w_orig, h_orig = img.size
        alvo_px = item['medida_cm'] * CM_TO_PX
        
        if h_orig > w_orig:
            img = img.resize((int(w_orig * (alvo_px / h_orig)), int(alvo_px)), Image.LANCZOS)
        else:
            img = img.resize((int(alvo_px), int(h_orig * (alvo_px / w_orig))), Image.LANCZOS)
            
        peca_visual, peca_mask = gerar_contorno_individual(img, item['sangria'], item['linha'])
        
        for _ in range(item['quantidade']):
            all_pieces.append({'img': peca_visual, 'mask': peca_mask})

    # 2. Organizar em Múltiplas Folhas
    folhas = []
    pecas_nao_alocadas = all_pieces.copy()
    modo = "Linhas" if len(lista_config) == 1 else "Tetris"

    while pecas_nao_alocadas and len(folhas) < 15:
        canvas = Image.new("RGB", (A4_WIDTH, A4_HEIGHT), (255, 255, 255))
        mask_canvas = Image.new("L", (A4_WIDTH, A4_HEIGHT), 0)
        ainda_cabem = []
        
        if modo == "Linhas":
            cx, cy, lh = m_px, m_px, 0
            for i, p in enumerate(pecas_nao_alocadas):
                iw, ih = p['img'].size
                if cx + iw + m_px > A4_WIDTH:
                    cx = m_px
                    cy += lh + e_px
                    lh = 0
                if cy + ih + m_px <= A4_HEIGHT:
                    canvas.paste(p['img'], (cx, cy), p['img'])
                    mask_canvas.paste(p['mask'], (cx, cy), p['mask'])
                    cx += iw + e_px
                    lh = max(lh, ih)
                else:
                    ainda_cabem = pecas_nao_alocadas[i:]
                    break
        else:
            for p in pecas_nao_alocadas:
                iw, ih = p['img'].size
                encaixou = False
                for _ in range(800): 
                    tx = random.randint(m_px, A4_WIDTH - iw - m_px)
                    ty = random.randint(m_px, A4_HEIGHT - ih - m_px)
                    if not ImageChops.multiply(mask_canvas.crop((tx, ty, tx+iw, ty+ih)), p['mask']).getbbox():
                        canvas.paste(p['img'], (tx, ty), p['img'])
                        mask_canvas.paste(p['mask'], (tx, ty), p['mask'])
                        encaixou = True
                        break
                if not encaixou: ainda_cabem.append(p)
        
        folhas.append(canvas)
        pecas_nao_alocadas = ainda_cabem

    return folhas

# --- Interface ---
st.set_page_config(page_title="ScanNCut Studio Smart", layout="wide")
st.title("✂️ ScanNCut Pro: Contorno Individual")

with st.sidebar:
    st.header("Configuração da Folha")
    margem = st.slider("Margem Papel (cm)", 0.3, 1.0, 0.5)
    st.info("💡 Agora você define a sangria de cada imagem separadamente abaixo.")

u = st.file_uploader("Suba seus PNGs", type="png", accept_multiple_files=True)
if u:
    confs = []
    for i, f in enumerate(u):
        with st.expander(f"Configurar: {f.name}", expanded=True):
            col1, col2, col3 = st.columns([1, 2, 2])
            img = Image.open(f)
            with col1:
                st.image(img, width=100)
            with col2:
                med = st.number_input(f"Maior Lado (cm)", 1.0, 20.0, 5.0, key=f"m{i}")
                qtd = st.number_input(f"Qtd", 1, 100, 10, key=f"q{i}")
            with col3:
                sang = st.selectbox("Sangria", [0.0, 0.2, 0.3, 0.5], index=2, key=f"s{i}")
                lin = st.checkbox("Linha Preta", value=True, key=f"l{i}")
                mir = st.checkbox("Mirror", key=f"r{i}")
            
            confs.append({
                'img': img, 
                'medida_cm': med, 
                'quantidade': qtd, 
                'espelhar': mir, 
                'sangria': sang, 
                'linha': lin
            })

    if st.button("🚀 GERAR PROJETO PERSONALIZADO"):
        folhas = montar_projeto(confs, margem)
        if folhas:
            st.success(f"Projeto Gerado!")
            for i, f in enumerate(folhas):
                st.image(f, caption=f"Página {i+1}", use_container_width=True)
            
            out = io.BytesIO()
            folhas[0].save(out, format="PDF", save_all=True, append_images=folhas[1:], resolution=300.0)
            st.download_button("📥 Baixar PDF", out.getvalue(), "projeto_scanncut.pdf")
