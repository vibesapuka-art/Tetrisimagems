import streamlit as st
from PIL import Image, ImageFilter
import io

# --- CONFIGURAÇÕES TÉCNICAS (PADRÃO A4 300 DPI) ---
A4_WIDTH, A4_HEIGHT = 2480, 3508
CM_TO_PX = 118.11 

def tornar_impar(n):
    """Garante que o raio do filtro seja ímpar para o processamento de imagem."""
    n = int(n)
    return n if n % 2 != 0 else n + 1

# --- INICIALIZAÇÃO DO BANCO DE DADOS TEMPORÁRIO (SESSION STATE) ---
if 'galeria' not in st.session_state:
    st.session_state.galeria = []

# --- MOTOR DE PROCESSAMENTO DE IMAGEM ---
def gerar_contorno_individual(img, tipo_contorno, sangria_escolhida, linha_ativa, nivel_suavidade, espessura_linha_mm):
    bbox_original = img.getbbox()
    if bbox_original:
        img = img.crop(bbox_original)
    img = img.convert("RGBA")

    if tipo_contorno == "Corte no Desenho (0mm)":
        distancia_px = 2 
    else:
        num_mm = float(sangria_escolhida.replace('mm', ''))
        distancia_px = int((num_mm / 10) * CM_TO_PX)
    
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
        img_res = img_base.resize((int(w*(alvo_px/h)), int(alvo_px)) if h>w else (int(alvo_px), int(h*(alvo_px/w))), Image.LANCZOS)
        pv = gerar_contorno_individual(img_res, item['tipo'], item['sangria_val'], item['linha'], nivel_suavidade, espessura_linha)
        for _ in range(item['quantidade']): all_pieces.append(pv)

    folhas = []
    pecas_restantes = all_pieces.copy()
    while pecas_restantes and len(folhas) < 30:
        temp_canvas = Image.new("RGBA", (A4_WIDTH, A4_HEIGHT), (0,0,0,0))
        cx, cy, lh = m_px, m_px, 0
        ainda_cabem = []
        for p in pecas_restantes:
            iw, ih = p.size
            if cx + iw > A4_WIDTH - m_px: cx, cy, lh = m_px, cy + lh + e_px, 0
            if cy + ih <= A4_HEIGHT - m_px:
                temp_canvas.paste(p, (cx, cy), p)
                cx, lh = cx + iw + e_px, max(lh, ih)
            else: ainda_cabem.append(p)
        if temp_canvas.getbbox():
            f_p = Image.new("RGB", (A4_WIDTH, A4_HEIGHT), (255, 255, 255))
            f_p.paste(temp_canvas, (0, 0), temp_canvas)
            folhas.append(f_p)
        pecas_restantes = ainda_cabem
    return folhas

# --- INTERFACE STREAMLIT ---
st.set_page_config(page_title="Bazzott Lov´s Editor", layout="wide")
st.title("✂️ Bazzott Lov´s Editor")

# Barra Lateral
with st.sidebar:
    st.header("⚙️ 1. Ajustes Globais")
    espessura_linha = st.slider("Linha (mm)", 0.1, 5.0, 0.3)
    suavidade = st.slider("Arredondamento", 0, 30, 30)
    margem = st.slider("Margem (cm)", 0.5, 2.5, 1.0)
    
    st.divider()
    st.header("📦 2. Sincronização em Massa")
    b_size = st.number_input("Tamanho Padrão (cm)", 1.0, 25.0, 5.0)
    b_qtd = st.number_input("Quantidade Padrão", 1, 100, 1)
    lista_sangrias = ["2mm", "3mm", "5mm", "7mm", "9mm"]
    b_sangria = st.selectbox("Sangria Padrão", lista_sangrias, index=4) # 9mm por padrão
    
    if st.button("🔄 Aplicar a Todos"):
        for i in range(len(st.session_state.galeria)):
            st.session_state[f"m{i}"] = b_size
            st.session_state[f"q{i}"] = b_qtd
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
        # Só adiciona se o arquivo já não estiver na galeria para evitar duplicidade ao recarregar
        if f.name not in [img['name'] for img in st.session_state.galeria]:
            st.session_state.galeria.append({"name": f.name, "img": Image.open(f)})

# Galeria de Configurações
if st.session_state.galeria:
    confs = []
    for i, item in enumerate(st.session_state.galeria):
        with st.expander(f"📦 {item['name']}", expanded=True):
            c1, c2, c3 = st.columns([1, 2, 2])
            with c1: 
                st.image(item['img'], width=80)
            with c2:
                med = st.number_input(f"Tamanho (cm)", 1.0, 25.0, key=f"m{i}", value=st.session_state.get(f"m{i}", 5.0))
                qtd = st.number_input(f"Quantidade", 1, 100, key=f"q{i}", value=st.session_state.get(f"q{i}", 1))
            with c3:
                tipo = st.selectbox("Corte", ["Com Sangria", "Corte no Desenho (0mm)"], key=f"t{i}")
                # Busca o valor no session_state ou usa 9mm (index 4) como padrão inicial
                idx_atual = lista_sangrias.index(st.session_state[f"s{i}"]) if f"s{i}" in st.session_state else 4
                sang = st.selectbox("Sangria", lista_sangrias, index=idx_atual, key=f"s{i}")
                lin = st.checkbox("Linha Preta", True, key=f"l{i}")
            
            confs.append({'img': item['img'], 'medida_cm': med, 'quantidade': qtd, 'tipo': tipo, 'sangria_val': sang, 'linha': lin})

    # Botão de Processamento Final
    st.divider()
    if st.button("🚀 GERAR PDF FINAL", use_container_width=True):
        with st.spinner("Gerando layout..."):
            folhas = montar_projeto(confs, margem, suavidade, espessura_linha)
            if folhas:
                for idx, f in enumerate(folhas): 
                    st.image(f, caption=f"Página {idx+1}", use_container_width=True)
                
                pdf_bytes = io.BytesIO()
                folhas[0].save(pdf_bytes, format="PDF", save_all=True, append_images=folhas[1:], resolution=300.0)
                st.download_button("📥 Baixar PDF para ScanNCut", pdf_bytes.getvalue(), "Bazzott_Lovs_Editor.pdf", use_container_width=True)
