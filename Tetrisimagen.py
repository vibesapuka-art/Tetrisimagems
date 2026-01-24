import streamlit as st
from PIL import Image, ImageFilter, ImageOps
import io

# --- CONFIGURAÇÕES TÉCNICAS (PADRÃO A4 300 DPI) ---
A4_WIDTH, A4_HEIGHT = 2480, 3508
CM_TO_PX = 118.11 

def tornar_impar(n):
    """Garante que o raio do filtro seja ímpar para o processamento de imagem."""
    n = int(n)
    return n if n % 2 != 0 else n + 1

# --- MOTOR DE PROCESSAMENTO DE IMAGEM ---
def gerar_contorno_individual(img, tipo_contorno, sangria_cm, linha_ativa, nivel_suavidade, espessura_linha_mm, espelhar=False):
    img = img.convert("RGBA")
    bbox_original = img.getbbox()
    if bbox_original:
        img = img.crop(bbox_original)
    
    # Aplica espelhamento se a opção estiver ativa
    if espelhar:
        img = ImageOps.mirror(img)

    if tipo_contorno == "Corte no Desenho (0mm)":
        distancia_px = 2 
    else:
        distancia_px = int(sangria_cm * CM_TO_PX)
    
    linha_px = int((espessura_linha_mm / 10) * CM_TO_PX)
    fator = 0.5 
    img_s = img.resize((int(img.width * fator), int(img.height * fator)), Image.LANCZOS)
    p_px_s = int(distancia_px * fator)
    l_px_s = int(linha_px * fator)
    
    respiro = (p_px_s + l_px_s) * 2 + 120
    alpha_base = Image.new("L", (img_s.width + respiro, img_s.height + respiro), 0)
    alpha_base.paste(img_s.split()[3], (respiro // 2, respiro // 2))
    
    mask = alpha_base.filter(ImageFilter.MaxFilter(tornar_impar(p_px_s)))
    if nivel_suavidade > 0:
        mask = mask.filter(ImageFilter.GaussianBlur(radius=nivel_suavidade * fator))
        mask = mask.point(lambda p: 255 if p > 128 else 0)

    mask_linha = mask.filter(ImageFilter.MaxFilter(tornar_impar(l_px_s if l_px_s > 0 else 1)))
    mask_f = mask.resize((img.width + distancia_px*2 + 180, img.height + distancia_px*2 + 180), Image.LANCZOS)
    mask_f = mask_f.point(lambda p: 255 if p > 128 else 0)
    mask_l_f = mask_linha.resize(mask_f.size, Image.LANCZOS)
    mask_l_f = mask_l_f.point(lambda p: 255 if p > 128 else 0)

    final_rgba = Image.new("RGBA", mask_f.size, (0, 0, 0, 0))
    if tipo_contorno == "Com Sangria":
        final_rgba.paste((255, 255, 255, 255), (0, 0), mask_f)
    
    if linha_ativa:
        final_rgba.paste((0, 0, 0, 255), (0, 0), mask_l_f)
        interior_limpo = mask_f.filter(ImageFilter.MinFilter(3))
        final_rgba.paste((0,0,0,0), (0,0), interior_limpo)
    
    pos_x, pos_y = (mask_f.width - img.width) // 2, (mask_f.height - img.height) // 2
    img_top = Image.new("RGBA", mask_f.size, (0, 0, 0, 0))
    img_top.paste(img, (pos_x, pos_y))
    final_rgba = Image.alpha_composite(final_rgba, img_top)
    return final_rgba.crop(final_rgba.getbbox())

# --- FUNÇÃO DE MONTAGEM NO A4 ---
def montar_projeto(lista_config, margem_cm, nivel_suavidade, espessura_linha):
    m_px, e_px = int(margem_cm * CM_TO_PX), int(0.15 * CM_TO_PX)
    all_pieces = []
    
    for item in lista_config:
        img_base = item['img'].convert("RGBA")
        alvo_px = item['medida_cm'] * CM_TO_PX
        w, h = img_base.size
        # Mantém proporção
        img_res = img_base.resize((int(w*(alvo_px/h)), int(alvo_px)) if h>w else (int(alvo_px), int(h*(alvo_px/w))), Image.LANCZOS)
        
        # Gera Peças Normais
        if item['quantidade'] > 0:
            pv_normal = gerar_contorno_individual(img_res, item['tipo'], item['sangria_val'], item['linha'], nivel_suavidade, espessura_linha, espelhar=False)
            for _ in range(item['quantidade']): 
                all_pieces.append(pv_normal)
        
        # Gera Peças Espelhadas (Clones)
        if item['quantidade_espelho'] > 0:
            pv_espelho = gerar_contorno_individual(img_res, item['tipo'], item['sangria_val'], item['linha'], nivel_suavidade, espessura_linha, espelhar=True)
            for _ in range(item['quantidade_espelho']): 
                all_pieces.append(pv_espelho)

    folhas = []
    pecas_restantes = all_pieces.copy()
    while pecas_restantes and len(folhas) < 30:
        temp_canvas = Image.new("RGBA", (A4_WIDTH, A4_HEIGHT), (0,0,0,0))
        cx, cy, lh = m_px, m_px, 0
        inseridos_nesta_folha = []
        pecas_nao_couberam = []
        
        for p in pecas_restantes:
            iw, ih = p.size
            if cx + iw > A4_WIDTH - m_px: 
                cx, cy, lh = m_px, cy + lh + e_px, 0
            
            if cy + ih <= A4_HEIGHT - m_px:
                temp_canvas.paste(p, (cx, cy), p)
                cx, lh = cx + iw + e_px, max(lh, ih)
            else:
                pecas_nao_couberam.append(p)
        
        if temp_canvas.getbbox():
            f_p = Image.new("RGB", (A4_WIDTH, A4_HEIGHT), (255, 255, 255))
            f_p.paste(temp_canvas, (0, 0), temp_canvas)
            folhas.append(f_p)
        
        pecas_restantes = pecas_nao_couberam
        if not pecas_nao_couberam: break
        
    return folhas

# --- INTERFACE STREAMLIT ---
st.set_page_config(page_title="Bazzott Love Edit", layout="wide")
st.title("✂️ Bazzott Love Edit")

if 'galeria' not in st.session_state:
    st.session_state.galeria = []

# Barra Lateral
with st.sidebar:
    st.header("⚙️ 1. Ajustes Globais")
    espessura_linha = st.slider("Espessura Linha (mm)", 0.1, 5.0, 0.3)
    suavidade = st.slider("Arredondamento/Suavização", 0, 30, 15)
    margem = st.slider("Margem da Folha (cm)", 0.5, 2.5, 1.0)
    
    st.divider()
    st.header("📦 2. Sincronização em Massa")
    b_size = st.number_input("Tamanho Padrão (cm)", 1.0, 25.0, 5.0)
    b_qtd = st.number_input("Qtd Padrão (Normal)", 1, 100, 1)
    b_qtd_e = st.number_input("Qtd Padrão (Espelho)", 0, 100, 0)
    b_sangria = st.slider("Sangria Padrão (cm)", 0.1, 1.0, 0.5)
    
    if st.button("🔄 Aplicar a Todos da Galeria"):
        for i in range(len(st.session_state.galeria)):
            st.session_state[f"m{i}"] = b_size
            st.session_state[f"q{i}"] = b_qtd
            st.session_state[f"qe{i}"] = b_qtd_e
            st.session_state[f"s{i}"] = b_sangria
        st.rerun()

    st.divider()
    if st.button("🗑️ Limpar Galeria"):
        st.session_state.galeria = []
        st.rerun()

# Área de Upload
u = st.file_uploader("Upload de arquivos PNG", type="png", accept_multiple_files=True)
if u:
    for f in u:
        if f.name not in [img['name'] for img in st.session_state.galeria]:
            st.session_state.galeria.append({"name": f.name, "img": Image.open(f)})

# Galeria de Configurações
if st.session_state.galeria:
    confs = []
    for i, item in enumerate(st.session_state.galeria):
        with st.expander(f"🖼️ Configurar: {item['name']}", expanded=True):
            c1, c2, c3 = st.columns([1, 2, 2])
            with c1: 
                st.image(item['img'], width=100)
            with c2:
                med = st.number_input(f"Tamanho (cm)", 1.0, 25.0, key=f"m{i}", value=st.session_state.get(f"m{i}", 5.0))
                qtd = st.number_input(f"Quantidade Normal", 1, 100, key=f"q{i}", value=st.session_state.get(f"q{i}", 1))
                qtd_e = st.number_input(f"Quantidade Espelhada", 0, 100, key=f"qe{i}", value=st.session_state.get(f"qe{i}", 0))
            with c3:
                tipo = st.selectbox("Tipo de Corte", ["Com Sangria", "Corte no Desenho (0mm)"], key=f"t{i}")
                sang = st.slider("Sangria (cm)", 0.1, 1.0, key=f"s{i}", value=st.session_state.get(f"s{i}", 0.5))
                lin = st.checkbox("Linha de Corte (Preta)", True, key=f"l{i}")
            
            confs.append({
                'img': item['img'], 
                'medida_cm': med, 
                'quantidade': qtd, 
                'quantidade_espelho': qtd_e,
                'tipo': tipo, 
                'sangria_val': sang, 
                'linha': lin
            })

    # Botão de Processamento Final
    st.divider()
    if st.button("🚀 GERAR PDF (BAZZOTT LOVE EDIT)", use_container_width=True):
        with st.spinner("Calculando layout e gerando sangrias..."):
            folhas = montar_projeto(confs, margem, suavidade, espessura_linha)
            if folhas:
                for idx, f in enumerate(folhas): 
                    st.image(f, caption=f"Página {idx+1}", use_container_width=True)
                
                pdf_bytes = io.BytesIO()
                folhas[0].save(pdf_bytes, format="PDF", save_all=True, append_images=folhas[1:], resolution=300.0)
                st.download_button("📥 Baixar PDF Final", pdf_bytes.getvalue(), "Bazzott_Love_Edit.pdf", use_container_width=True)
