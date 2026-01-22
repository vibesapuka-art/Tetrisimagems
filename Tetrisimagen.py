import streamlit as st
from PIL import Image, ImageFilter
import io

# --- CONSTANTES DE PRECISÃO (300 DPI) ---
# 1 cm = 118.11 pixels em 300 DPI
CM_TO_PX = 118.11 
A4_WIDTH_PX = 2480  
A4_HEIGHT_PX = 3508 

def tornar_impar(n):
    n = int(n)
    return n if n % 2 != 0 else n + 1

# Inicializa a galeria na memória
if 'galeria' not in st.session_state:
    st.session_state.galeria = []

# --- MOTOR DE PROCESSAMENTO DE IMAGEM ---
def gerar_contorno_individual(img, medida_cm, tipo_contorno, sangria_val, linha_ativa, suavidade, espessura_mm):
    # 1. Ajusta a imagem para o tamanho físico real solicitado
    alvo_px = int(medida_cm * CM_TO_PX)
    w, h = img.size
    if h > w:
        nova_alt = alvo_px
        nova_lar = int(w * (alvo_px / h))
    else:
        nova_lar = alvo_px
        nova_alt = int(h * (alvo_px / w))
    
    img = img.resize((nova_lar, nova_alt), Image.LANCZOS).convert("RGBA")
    
    # 2. Calcula sangria e linha em pixels
    if tipo_contorno == "Corte no Desenho (0mm)":
        dist_px = 2
    else:
        dist_px = int((float(sangria_val.replace('mm','')) / 10) * CM_TO_PX)
    
    linha_px = int((espessura_mm / 10) * CM_TO_PX)
    
    # 3. Criação da máscara (Sangria + Linha)
    padding = dist_px + linha_px + 20
    canvas_w, canvas_h = img.width + padding*2, img.height + padding*2
    alpha = Image.new("L", (canvas_w, canvas_h), 0)
    alpha.paste(img.split()[3], (padding, padding))
    
    mask_sangria = alpha.filter(ImageFilter.MaxFilter(tornar_impar(dist_px)))
    if suavidade > 0:
        mask_sangria = mask_sangria.filter(ImageFilter.GaussianBlur(suavidade/4))
        mask_sangria = mask_sangria.point(lambda p: 255 if p > 128 else 0)
        
    mask_linha = mask_sangria.filter(ImageFilter.MaxFilter(tornar_impar(linha_px)))

    # 4. Composição Final
    peca = Image.new("RGBA", (canvas_w, canvas_h), (0,0,0,0))
    if tipo_contorno == "Com Sangria":
        peca.paste((255,255,255,255), (0,0), mask_sangria)
    
    if linha_ativa:
        peca.paste((0,0,0,255), (0,0), mask_linha)
        # Corta o meio da linha para ela ficar fina
        peca.paste((0,0,0,0), (0,0), mask_sangria.filter(ImageFilter.MinFilter(3)))

    peca.paste(img, (padding, padding), img)
    return peca.crop(peca.getbbox())

# --- FUNÇÃO DE MONTAGEM DAS FOLHAS ---
def montar_folhas(pecas, margem_cm):
    margem_px = int(margem_cm * CM_TO_PX)
    espacamento_px = int(0.15 * CM_TO_PX)
    
    folhas_geradas = []
    restante = pecas.copy()
    
    while restante:
        canvas = Image.new("RGBA", (A4_WIDTH_PX, A4_HEIGHT_PX), (0,0,0,0))
        x, y, h_linha = margem_px, margem_px, 0
        indices_usados = []
        
        for i, p in enumerate(restante):
            pw, ph = p.size
            if x + pw > A4_WIDTH_PX - margem_px:
                x = margem_px
                y += h_linha + espacamento_px
                h_linha = 0
            
            if y + ph <= A4_HEIGHT_PX - margem_px:
                canvas.paste(p, (x, y), p)
                x += pw + espacamento_px
                h_linha = max(h_linha, ph)
                indices_usados.append(i)
            else:
                break
        
        if not indices_usados: break
            
        for idx in sorted(indices_usados, reverse=True):
            restante.pop(idx)
            
        # Finalização e Centralização
        bbox = canvas.getbbox()
        folha_branca = Image.new("RGB", (A4_WIDTH_PX, A4_HEIGHT_PX), (255,255,255))
        if bbox:
            w_c, h_c = bbox[2]-bbox[0], bbox[3]-bbox[1]
            off_x = (A4_WIDTH_PX - w_c) // 2 - bbox[0]
            off_y = (A4_HEIGHT_PX - h_c) // 2 - bbox[1]
            folha_branca.paste(canvas, (off_x, off_y), canvas)
        folhas_geradas.append(folha_branca)
        
    return folhas_geradas

# --- INTERFACE ---
st.set_page_config(page_title="Bazzott Lov´s Editor", layout="wide")
st.title("✂️ Bazzott Lov´s Editor - Versão Pro Precisão")

with st.sidebar:
    st.header("⚙️ Ajustes Globais")
    m_cm = st.slider("Margem da Folha (cm)", 0.5, 2.0, 1.0)
    lin_mm = st.slider("Linha de Corte (mm)", 0.1, 1.0, 0.3)
    suave = st.slider("Arredondamento", 0, 30, 20)
    
    st.divider()
    st.header("📦 Sincronização em Massa")
    b_size = st.number_input("Tamanho Tag (cm)", 1.0, 25.0, 4.0)
    b_qtd = st.number_input("Quantidade Total", 1, 500, 20)
    list_s = ["2mm", "3mm", "5mm", "7mm", "9mm"]
    b_sang = st.selectbox("Sangria Padrão", list_s, index=4)

    if st.button("🔄 Aplicar a Todos"):
        for i in range(len(st.session_state.galeria)):
            st.session_state[f"m{i}"] = b_size
            st.session_state[f"q{i}"] = b_qtd
            st.session_state[f"s{i}"] = b_sang
        st.rerun()

    if st.button("🗑️ Limpar Tudo"):
        st.session_state.galeria = []
        st.rerun()

u = st.file_uploader("Arraste seus PNGs", type="png", accept_multiple_files=True)
if u:
    for f in u:
        if f.name not in [img['name'] for img in st.session_state.galeria]:
            st.session_state.galeria.append({"name": f.name, "img": Image.open(f)})

if st.session_state.galeria:
    pecas_para_montar = []
    idx_del = None
    
    for i, item in enumerate(st.session_state.galeria):
        with st.expander(f"Configurar: {item['name']}", expanded=True):
            c1, c2, c3, c4 = st.columns([1, 2, 2, 0.5])
            with c1: st.image(item['img'], width=80)
            with c2:
                tam = st.number_input("Tam (cm)", 1.0, 25.0, key=f"m{i}", value=float(st.session_state.get(f"m{i}", 4.0)))
                qtd = st.number_input("Qtd", 1, 500, key=f"q{i}", value=int(st.session_state.get(f"q{i}", 1)))
            with c3:
                tipo = st.selectbox("Corte", ["Com Sangria", "Corte no Desenho (0mm)"], key=f"t{i}")
                san = st.selectbox("Sangria", list_s, key=f"s{i}", index=list_s.index(st.session_state.get(f"s{i}", "9mm")))
                lin = st.checkbox("Linha Preta", True, key=f"l{i}")
            with c4:
                if st.button("❌", key=f"del{i}"): idx_del = i
            
            # Prepara a peça individualmente para a fila de montagem
            p_processada = gerar_contorno_individual(item['img'], tam, tipo, san, lin, suave, lin_mm)
            for _ in range(qtd): pecas_para_montar.append(p_processada)

    if idx_del is not None:
        st.session_state.galeria.pop(idx_del)
        st.rerun()

    if st.button("🚀 GERAR PDF EM TAMANHO REAL", use_container_width=True):
        with st.spinner("Calculando espaço e gerando folhas..."):
            folhas = montar_folhas(pecas_para_montar, m_cm)
            if folhas:
                for idx, f in enumerate(folhas): st.image(f, caption=f"Página {idx+1}")
                pdf = io.BytesIO()
                folhas[0].save(pdf, format="PDF", save_all=True, append_images=folhas[1:], resolution=300.0)
                st.download_button("📥 Baixar PDF (Imprimir em Escala 100%)", pdf.getvalue(), "Bazzott_Lovs_Output.pdf")
