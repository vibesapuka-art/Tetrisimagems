import streamlit as st
from PIL import Image, ImageFilter, ImageOps
import io

# --- CONFIGURAÇÕES TÉCNICAS RÍGIDAS (300 DPI) ---
A4_WIDTH, A4_HEIGHT = 2480, 3508
CM_TO_PX = 118.11  # 1cm = 118.11 pixels em 300 DPI

def tornar_impar(n):
    n = int(n)
    return n if n % 2 != 0 else n + 1

# --- MOTOR DE PROCESSAMENTO (PRECISÃO 1:1) ---
def gerar_contorno_individual(img, tipo_contorno, sangria_cm, linha_ativa, nivel_suavidade, espessura_linha_mm, espelhar=False):
    img = img.convert("RGBA")
    bbox = img.getbbox()
    if bbox:
        img = img.crop(bbox)
    
    if espelhar:
        img = ImageOps.mirror(img)

    # 1. CRIAÇÃO DA MÁSCARA COM O TAMANHO REAL DA IMAGEM
    # A sangria é adicionada como um preenchimento (padding) externo
    dist_px = int(sangria_cm * CM_TO_PX) if tipo_contorno == "Com Sangria" else 2
    linha_px = int((espessura_linha_mm / 10) * CM_TO_PX)
    
    # Criamos um canvas maior para a sangria não cortar
    padding = dist_px + linha_px + 20
    canvas_w = img.width + (padding * 2)
    canvas_h = img.height + (padding * 2)
    
    alpha_base = Image.new("L", (canvas_w, canvas_h), 0)
    alpha_base.paste(img.split()[3], (padding, padding))
    
    # Gerar contorno da sangria
    mask = alpha_base.filter(ImageFilter.MaxFilter(tornar_impar(dist_px * 2)))
    if nivel_suavidade > 0:
        mask = mask.filter(ImageFilter.GaussianBlur(radius=nivel_suavidade / 2))
        mask = mask.point(lambda p: 255 if p > 128 else 0)

    # Preparar imagem final
    peca_final = Image.new("RGBA", (canvas_w, canvas_h), (0, 0, 0, 0))
    
    # Aplicar Fundo Branco da Sangria
    if tipo_contorno == "Com Sangria":
        peca_final.paste((255, 255, 255, 255), (0, 0), mask)
    
    # Aplicar Linha de Corte
    if linha_ativa:
        mask_linha = mask.filter(ImageFilter.MaxFilter(tornar_impar(linha_px)))
        peca_final.paste((0, 0, 0, 255), (0, 0), mask_linha)
        # Limpa o interior para a linha não vazar para dentro do desenho
        interior = mask.filter(ImageFilter.MinFilter(3))
        peca_final.paste((0,0,0,0), (0,0), interior)

    # Colar a imagem original por cima (centralizada)
    peca_final.paste(img, (padding, padding), img)
    
    return peca_final.crop(peca_final.getbbox())

# --- FUNÇÃO DE MONTAGEM (SEM REDIMENSIONAMENTO EXTRA) ---
def montar_projeto(lista_config, margem_cm, nivel_suavidade, espessura_linha):
    m_px = int(margem_cm * CM_TO_PX)
    e_px = 5 # Pequeno espaço de respiro entre peças
    all_pieces = []
    
    for item in lista_config:
        img_base = item['img'].convert("RGBA")
        # TAMANHO REAL DESEJADO
        alvo_px = item['medida_cm'] * CM_TO_PX
        w, h = img_base.size
        
        # Redimensiona a imagem base UMA VEZ para o tamanho de CM escolhido
        if h > w:
            new_h = int(alvo_px)
            new_w = int(w * (alvo_px / h))
        else:
            new_w = int(alvo_px)
            new_h = int(h * (alvo_px / w))
        
        img_res = img_base.resize((new_w, new_h), Image.LANCZOS)
        
        # Gera as versões normal e espelhada
        if item['quantidade'] > 0:
            p_n = gerar_contorno_individual(img_res, item['tipo'], item['sangria_val'], item['linha'], nivel_suavidade, espessura_linha, False)
            for _ in range(item['quantidade']): all_pieces.append(p_n)
        
        if item['quantidade_espelho'] > 0:
            p_e = gerar_contorno_individual(img_res, item['tipo'], item['sangria_val'], item['linha'], nivel_suavidade, espessura_linha, True)
            for _ in range(item['quantidade_espelho']): all_pieces.append(p_e)

    folhas = []
    while all_pieces:
        folha = Image.new("RGB", (A4_WIDTH, A4_HEIGHT), (255, 255, 255))
        cx, cy, lh = m_px, m_px, 0
        removidos = []
        
        for i, p in enumerate(all_pieces):
            pw, ph = p.size
            if cx + pw > A4_WIDTH - m_px:
                cx = m_px
                cy += lh + e_px
                lh = 0
            
            if cy + ph <= A4_HEIGHT - m_px:
                folha.paste(p, (cx, cy), p)
                cx += pw + e_px
                lh = max(lh, ph)
                removidos.append(i)
            else:
                break
        
        folhas.append(folha)
        for index in sorted(removidos, reverse=True):
            all_pieces.pop(index)
            
    return folhas

# --- INTERFACE ---
st.set_page_config(page_title="Bazzott Love Edit", layout="wide")
st.title("✂️ Bazzott Love Edit - Precisão Real")

if 'galeria' not in st.session_state: st.session_state.galeria = []

with st.sidebar:
    st.header("⚙️ Ajustes Globais")
    espessura_linha = st.slider("Linha (mm)", 0.1, 5.0, 0.3)
    suavidade = st.slider("Arredondamento", 0, 30, 10)
    margem = st.slider("Margem Papel (cm)", 0.1, 1.5, 0.5)
    
    st.divider()
    st.header("📦 Sincronização em Massa")
    b_size = st.number_input("Tamanho (cm)", 1.0, 25.0, 4.0)
    b_qtd = st.number_input("Qtd Normal", 1, 100, 24)
    b_sangria = st.slider("Sangria (cm)", 0.0, 1.0, 0.1)
    
    if st.button("🔄 Aplicar a Todos"):
        for i in range(len(st.session_state.galeria)):
            st.session_state[f"m{i}"] = b_size
            st.session_state[f"q{i}"] = b_qtd
            st.session_state[f"s{i}"] = b_sangria
        st.rerun()

u = st.file_uploader("Upload PNG", type="png", accept_multiple_files=True)
if u:
    for f in u:
        if f.name not in [img['name'] for img in st.session_state.galeria]:
            st.session_state.galeria.append({"name": f.name, "img": Image.open(f)})

if st.session_state.galeria:
    confs = []
    for i, item in enumerate(st.session_state.galeria):
        with st.expander(f"🖼️ {item['name']}", expanded=True):
            c1, c2, c3 = st.columns([1, 2, 2])
            with c1: st.image(item['img'], width=80)
            with c2:
                med = st.number_input("Tamanho (cm)", 1.0, 25.0, key=f"m{i}", value=st.session_state.get(f"m{i}", 4.0))
                qtd = st.number_input("Qtd Normal", 0, 100, key=f"q{i}", value=st.session_state.get(f"q{i}", 24))
            with c3:
                sang = st.slider("Sangria (cm)", 0.0, 1.0, key=f"s{i}", value=st.session_state.get(f"s{i}", 0.1))
                qtd_e = st.number_input("Qtd Espelho", 0, 100, key=f"qe{i}", value=0)
                lin = st.checkbox("Linha Preta", True, key=f"l{i}")
            
            confs.append({'img': item['img'], 'medida_cm': med, 'quantidade': qtd, 'quantidade_espelho': qtd_e, 'tipo': "Com Sangria", 'sangria_val': sang, 'linha': lin})

    if st.button("🚀 GERAR PDF FINAL", use_container_width=True):
        folhas = montar_projeto(confs, margem, suavidade, espessura_linha)
        for idx, f in enumerate(folhas): st.image(f, caption=f"Página {idx+1}")
        pdf_out = io.BytesIO()
        folhas[0].save(pdf_out, format="PDF", save_all=True, append_images=folhas[1:], resolution=300.0)
        st.download_button("📥 Baixar PDF", pdf_out.getvalue(), "Bazzott_Love_Precision.pdf", use_container_width=True)
