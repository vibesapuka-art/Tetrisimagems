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

def gerar_contorno_individual(img, tipo_contorno, linha_ativa):
    if tipo_contorno == "Sem Contorno":
        alpha = img.split()[3].point(lambda p: 255 if p > 100 else 0)
        return img, alpha

    # 3mm de sangria real (aprox 35 pixels em 300 DPI)
    p_px = int(0.3 * CM_TO_PX) if tipo_contorno == "Com Sangria (3mm)" else 4 
    
    respiro = p_px * 2 + 80
    img_exp = Image.new("RGBA", (img.width + respiro, img.height + respiro), (0, 0, 0, 0))
    img_exp.paste(img, (respiro // 2, respiro // 2))
    
    alpha = img_exp.split()[3].point(lambda p: 255 if p > 100 else 0)
    
    # Gerar a bolha de contorno com expansão corrigida
    mask_corte = alpha.filter(ImageFilter.MaxFilter(tornar_impar(p_px)))
    mask_corte = mask_corte.filter(ImageFilter.GaussianBlur(2)).point(lambda p: 255 if p > 128 else 0)

    nova_img = Image.new("RGBA", img_exp.size, (0, 0, 0, 0))
    
    if linha_ativa:
        # Linha preta externa para guia de corte
        borda_ext = mask_corte.filter(ImageFilter.MaxFilter(5))
        nova_img.paste((0,0,0,255), (0,0), borda_ext)
    
    # Fundo branco da sangria
    nova_img.paste((255,255,255,255), (0,0), mask_corte)
    # Imagem original por cima
    nova_img.paste(img_exp, (0,0), img_exp)
    
    bbox = nova_img.getbbox()
    if bbox:
        # Máscara de colisão para o modo Tetris/Linhas não sobrepor
        mask_colisao = mask_corte.filter(ImageFilter.MaxFilter(3)).crop(bbox)
        return nova_img.crop(bbox), mask_colisao
    return nova_img, mask_corte

def montar_projeto(lista_config, margem_cm, modo_layout):
    m_px = int(margem_cm * CM_TO_PX)
    e_px = int(0.15 * CM_TO_PX) # Espaçamento entre peças
    all_pieces = []
    
    for item in lista_config:
        img = item['img'].convert("RGBA")
        if item['espelhar']: img = ImageOps.mirror(img)
        
        # Lógica do Maior Lado Sincronizado
        w_orig, h_orig = img.size
        alvo_px = item['medida_cm'] * CM_TO_PX
        
        if h_orig > w_orig:
            img = img.resize((int(w_orig * (alvo_px / h_orig)), int(alvo_px)), Image.LANCZOS)
        else:
            img = img.resize((int(alvo_px), int(h_orig * (alvo_px / w_orig))), Image.LANCZOS)
            
        peca_visual, peca_mask = gerar_contorno_individual(img, item['tipo'], item['linha'])
        
        for _ in range(item['quantidade']):
            all_pieces.append({'img': peca_visual, 'mask': peca_mask})

    folhas = []
    pecas_restantes = all_pieces.copy()

    while pecas_restantes and len(folhas) < 20:
        canvas = Image.new("RGB", (A4_WIDTH, A4_HEIGHT), (255, 255, 255))
        mask_canvas = Image.new("L", (A4_WIDTH, A4_HEIGHT), 0)
        ainda_cabem = []
        
        if modo_layout == "Modo Linhas":
            cx, cy, lh = m_px, m_px, 0
            for i, p in enumerate(pecas_restantes):
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
                    ainda_cabem = pecas_restantes[i:]
                    break
        else: # MODO TETRIS
            # Organiza do maior para o menor para melhor encaixe
            pecas_restantes.sort(key=lambda x: x['img'].size[0] * x['img'].size[1], reverse=True)
            for p in pecas_restantes:
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
        pecas_restantes = ainda_cabem

    return folhas

# --- INTERFACE ---
st.set_page_config(page_title="ScanNCut Studio v4", layout="wide")

# Inicialização de estados para Bulk Edit
if 'bulk_tipo' not in st.session_state: st.session_state.bulk_tipo = "Com Sangria (3mm)"
if 'bulk_lin' not in st.session_state: st.session_state.bulk_lin = True

st.title("✂️ ScanNCut Pro: Linhas & Tetris")

with st.sidebar:
    st.header("1. Layout")
    modo_layout = st.radio("Escolha o Modo", ["Modo Linhas", "Modo Tetris"])
    margem = st.slider("Margem Papel (cm)", 0.3, 1.0, 0.5)
    
    st.divider()
    st.header("2. Ajuste em Massa")
    b_size = st.number_input("Tamanho (Maior Lado)", 1.0, 25.0, 5.0)
    b_qtd = st.number_input("Quantidade Total", 1, 200, 10)
    b_tipo = st.selectbox("Tipo de Corte Geral", ["Sem Contorno", "Corte no Desenho (0mm)", "Com Sangria (3mm)"], index=2)
    b_lin = st.checkbox("Ativar Linha Preta", value=True)
    aplicar_todos = st.button("🪄 Aplicar em todos os PNGs")

u = st.file_uploader("Suba seus arquivos PNG", type="png", accept_multiple_files=True)

if u:
    confs = []
    for i, f in enumerate(u):
        with st.expander(f"⚙️ Configurar: {f.name}", expanded=True):
            col1, col2, col3 = st.columns([1, 2, 2])
            img = Image.open(f)
            
            # Valores padrão ou massa
            def_size = b_size if aplicar_todos else 5.0
            def_qtd = b_qtd if aplicar_todos else 1
            def_tipo = b_tipo if aplicar_todos else "Com Sangria (3mm)"
            def_lin = b_lin if aplicar_todos else True
            
            with col1: st.image(img, width=100)
            with col2:
                med = st.number_input(f"Medida (cm)", 1.0, 25.0, def_size, key=f"m{i}")
                qtd = st.number_input(f"Qtd", 1, 200, def_qtd, key=f"q{i}")
            with col3:
                tipo_c = st.selectbox("Corte", ["Sem Contorno", "Corte no Desenho (0mm)", "Com Sangria (3mm)"], 
                                      index=["Sem Contorno", "Corte no Desenho (0mm)", "Com Sangria (3mm)"].index(def_tipo), key=f"t{i}")
                lin_c = st.checkbox("Linha de Corte", value=def_lin, key=f"l{i}")
                mir_c = st.checkbox("Espelhar", key=f"r{i}")
            
            confs.append({'img': img, 'medida_cm': med, 'quantidade': qtd, 'espelhar': mir_c, 'tipo': tipo_c, 'linha': lin_c})

    if st.button("🚀 GERAR FOLHAS"):
        with st.spinner("Processando peças..."):
            folhas = montar_projeto(confs, margem, modo_layout)
            if folhas:
                st.success(f"Concluído! Foram geradas {len(folhas)} folha(s).")
                for idx, f in enumerate(folhas):
                    st.image(f, caption=f"Página {idx+1}", use_container_width=True)
                
                out = io.BytesIO()
                folhas[0].save(out, format="PDF", save_all=True, append_images=folhas[1:], resolution=300.0)
                st.download_button("📥 Baixar PDF Completo", out.getvalue(), "projeto_scanncut.pdf", use_container_width=True)
