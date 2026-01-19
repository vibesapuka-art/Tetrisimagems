import streamlit as st
from PIL import Image, ImageChops, ImageFilter, ImageOps
import io
import random
import time

# Configuração A4 300 DPI
A4_WIDTH = 2480
A4_HEIGHT = 3508
CM_TO_PX = 118.11 

def tornar_impar(n):
    n = int(n)
    return n if n % 2 != 0 else n + 1

# --- FUNÇÃO DE CONTORNO OTIMIZADA ---
def gerar_contorno_individual(img, tipo_contorno, sangria_escolhida, linha_ativa, nivel_suavidade):
    bbox_original = img.getbbox()
    if bbox_original:
        img = img.crop(bbox_original)

    if tipo_contorno == "Sem Contorno":
        alpha = img.split()[3].point(lambda p: 255 if p > 100 else 0)
        return img, alpha

    if tipo_contorno == "Corte no Desenho (0mm)":
        p_px = 6
    else:
        valor_cm = float(sangria_escolhida.replace('mm', '')) / 10
        p_px = int(valor_cm * CM_TO_PX)
    
    # Redução de escala para processamento rápido (50%)
    fator = 0.5
    img_small = img.resize((int(img.width * fator), int(img.height * fator)), Image.NEAREST)
    p_px_small = int(p_px * fator)

    respiro = p_px_small * 2 + 50
    img_exp = Image.new("RGBA", (img_small.width + respiro, img_small.height + respiro), (0, 0, 0, 0))
    img_exp.paste(img_small, (respiro // 2, respiro // 2))
    
    alpha = img_exp.split()[3].point(lambda p: 255 if p > 100 else 0)
    mask = alpha.filter(ImageFilter.MaxFilter(tornar_impar(p_px_small)))
    
    if nivel_suavidade > 0:
        mask = mask.filter(ImageFilter.GaussianBlur(radius=nivel_suavidade * fator))
        mask = mask.point(lambda p: 255 if p > 128 else 0)

    # Redimensiona de volta para o tamanho original
    mask_final = mask.resize((img.width + p_px*2 + 60, img.height + p_px*2 + 60), Image.LANCZOS)
    mask_final = mask_final.point(lambda p: 255 if p > 128 else 0)

    nova_img = Image.new("RGBA", mask_final.size, (0, 0, 0, 0))
    if linha_ativa:
        borda = mask_final.filter(ImageFilter.MaxFilter(5))
        nova_img.paste((0,0,0,255), (0,0), borda)
    
    nova_img.paste((255,255,255,255), (0,0), mask_final)
    pos_x = (nova_img.width - img.width) // 2
    pos_y = (nova_img.height - img.height) // 2
    nova_img.paste(img, (pos_x, pos_y), img)
    
    bbox = nova_img.getbbox()
    if bbox:
        return nova_img.crop(bbox), mask_final.crop(bbox)
    return nova_img, mask_final

# --- LÓGICA DE MONTAGEM COM BARRA DE PROGRESSO ---
def montar_projeto(lista_config, margem_cm, modo_layout, nivel_suavidade):
    m_px = int(margem_cm * CM_TO_PX)
    e_px = int(0.12 * CM_TO_PX)
    
    progresso = st.progress(0)
    status_text = st.empty()
    
    all_pieces = []
    
    # 1. Processamento das Peças Únicas (Cache)
    status_text.text("🎨 Processando contornos e suavização...")
    for i, item in enumerate(lista_config):
        img_base = item['img'].convert("RGBA")
        bbox = img_base.getbbox()
        if bbox: img_base = img_base.crop(bbox)
        if item['espelhar']: img_base = ImageOps.mirror(img_base)
        
        alvo_px = item['medida_cm'] * CM_TO_PX
        w, h = img_base.size
        if h > w:
            img_res = img_base.resize((int(w * (alvo_px / h)), int(alvo_px)), Image.LANCZOS)
        else:
            img_res = img_base.resize((int(alvo_px), int(h * (alvo_px / w))), Image.LANCZOS)
            
        peca_v, peca_m = gerar_contorno_individual(img_res, item['tipo'], item['sangria_val'], item['linha'], nivel_suavidade)
        
        for _ in range(item['quantidade']):
            all_pieces.append({'img': peca_v, 'mask': peca_m})
        
        progresso.progress(int((i + 1) / len(lista_config) * 30)) # Primeiros 30%

    folhas = []
    pecas_restantes = all_pieces.copy()
    num_total = len(all_pieces)

    # 2. Organização do Layout
    status_text.text("📏 Organizando peças na folha...")
    while pecas_restantes and len(folhas) < 20:
        canvas = Image.new("RGB", (A4_WIDTH, A4_HEIGHT), (255, 255, 255))
        mask_canvas = Image.new("L", (A4_WIDTH, A4_HEIGHT), 0)
        ainda_cabem = []
        
        if modo_layout == "Modo Linhas":
            cx, cy, lh = m_px, m_px, 0
            for p in pecas_restantes:
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
                    ainda_cabem.append(p)
        else: # MODO TETRIS
            pecas_restantes.sort(key=lambda x: x['img'].size[0] * x['img'].size[1], reverse=True)
            for p in pecas_restantes:
                iw, ih = p['img'].size
                encaixou = False
                for _ in range(350): # Otimizado para velocidade
                    tx = random.randint(m_px, A4_WIDTH - iw - m_px)
                    ty = random.randint(m_px, A4_HEIGHT - ih - m_px)
                    if not ImageChops.multiply(mask_canvas.crop((tx, ty, tx+iw, ty+ih)), p['mask']).getbbox():
                        canvas.paste(p['img'], (tx, ty), p['img'])
                        mask_canvas.paste(p['mask'], (tx, ty), p['mask'])
                        encaixou = True
                        break
                if not encaixou: ainda_cabem.append(p)
        
        folhas.append(canvas)
        percent = int(30 + (1 - len(ainda_cabem)/num_total) * 60)
        progresso.progress(min(percent, 90))
        pecas_restantes = ainda_cabem

    status_text.text("📄 Gerando PDF final...")
    progresso.progress(100)
    time.sleep(0.5)
    progresso.empty()
    status_text.empty()
    return folhas

# --- INTERFACE ---
st.set_page_config(page_title="ScanNCut Fast Pro", layout="wide")
st.title("✂️ ScanNCut Pro: Versão Ultra-Rápida")

if 'uploads' not in st.session_state: st.session_state.uploads = []

with st.sidebar:
    st.header("Configurações")
    suavidade = st.slider("Arredondamento (Suavizar)", 0, 30, 15)
    modo_layout = st.radio("Layout", ["Modo Linhas", "Modo Tetris"])
    margem = st.slider("Margem (cm)", 0.3, 1.0, 0.5)
    st.divider()
    st.header("Ajuste em Massa")
    b_size = st.number_input("Tam (cm)", 1.0, 25.0, 5.0)
    b_qtd = st.number_input("Qtd", 1, 200, 10)
    b_sang = st.selectbox("Sangria", ["3mm", "5mm", "7mm", "9mm"])
    b_tipo = st.selectbox("Corte", ["Sem Contorno", "Corte no Desenho (0mm)", "Com Sangria"], index=2)
    b_lin = st.checkbox("Linha Preta", value=True)
    
    if st.button("🪄 Sincronizar"):
        for i in range(len(st.session_state.uploads)):
            st.session_state[f"m{i}"] = b_size
            st.session_state[f"q{i}"] = b_qtd
            st.session_state[f"t{i}"] = b_tipo
            if b_tipo == "Com Sangria": st.session_state[f"s{i}"] = b_sang
            st.session_state[f"l{i}"] = b_lin
        st.success("Sincronizado!")

u = st.file_uploader("Upload PNGs", type="png", accept_multiple_files=True)
if u:
    st.session_state.uploads = u
    confs = []
    for i, f in enumerate(u):
        with st.expander(f"⚙️ {f.name}", expanded=False):
            col1, col2, col3 = st.columns([1, 2, 2])
            img = Image.open(f)
            with col1: st.image(img, width=80)
            with col2:
                med = st.number_input(f"Tam (cm)", 1.0, 25.0, key=f"m{i}")
                qtd = st.number_input(f"Qtd", 1, 200, key=f"q{i}")
            with col3:
                tipo_c = st.selectbox("Corte", ["Sem Contorno", "Corte no Desenho (0mm)", "Com Sangria"], key=f"t{i}")
                sang_mm = st.selectbox("Sangria", ["3mm", "5mm", "7mm", "9mm"], key=f"s{i}") if tipo_c == "Com Sangria" else "0mm"
                lin_c = st.checkbox("Linha", key=f"l{i}")
                mir_c = st.checkbox("Mirror", key=f"r{i}")
            confs.append({'img': img, 'medida_cm': med, 'quantidade': qtd, 'espelhar': mir_c, 'tipo': tipo_c, 'sangria_val': sang_mm, 'linha': lin_c})

    if st.button("🚀 GERAR PROJETO"):
        folhas = montar_projeto(confs, margem, modo_layout, suavidade)
        if folhas:
            for idx, f in enumerate(folhas): st.image(f, caption=f"Página {idx+1}", use_container_width=True)
            out = io.BytesIO()
            folhas[0].save(out, format="PDF", save_all=True, append_images=folhas[1:], resolution=300.0)
            st.download_button("📥 Baixar PDF", out.getvalue(), "projeto.pdf", use_container_width=True)
