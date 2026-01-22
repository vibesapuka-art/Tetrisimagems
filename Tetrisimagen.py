import streamlit as st
from PIL import Image, ImageChops, ImageFilter, ImageOps, ImageDraw
import io

# --- CONFIGURAÇÕES TÉCNICAS (PADRÃO A4 300 DPI) ---
A4_WIDTH, A4_HEIGHT = 2480, 3508
CM_TO_PX = 118.11 

def tornar_impar(n):
    """Garante que o raio do filtro seja ímpar para o MaxFilter do Pillow."""
    n = int(n)
    return n if n % 2 != 0 else n + 1

# --- MOTOR DE PROCESSAMENTO DE IMAGEM ---
def gerar_contorno_individual(img, tipo_contorno, sangria_escolhida, linha_ativa, nivel_suavidade, espessura_linha_mm):
    # 1. Remove excesso de transparência ao redor da imagem original
    bbox_original = img.getbbox()
    if bbox_original:
        img = img.crop(bbox_original)
    img = img.convert("RGBA")

    # 2. Define distância da sangria
    if tipo_contorno == "Corte no Desenho (0mm)":
        distancia_px = 2 
    else:
        num_mm = float(sangria_escolhida.replace('mm', ''))
        distancia_px = int((num_mm / 10) * CM_TO_PX)
    
    # 3. Define espessura da linha preta
    linha_px = int((espessura_linha_mm / 10) * CM_TO_PX)
    
    # Redimensionamento temporário para suavizar o processamento
    fator = 0.5 
    img_s = img.resize((int(img.width * fator), int(img.height * fator)), Image.LANCZOS)
    p_px_s = int(distancia_px * fator)
    l_px_s = int(linha_px * fator)
    
    # Criação do canvas da máscara
    respiro = (p_px_s + l_px_s) * 2 + 120
    alpha_base = Image.new("L", (img_s.width + respiro, img_s.height + respiro), 0)
    alpha_base.paste(img_s.split()[3], (respiro // 2, respiro // 2))
    
    # Gerar área da Sangria
    mask = alpha_base.filter(ImageFilter.MaxFilter(tornar_impar(p_px_s)))
    if nivel_suavidade > 0:
        mask = mask.filter(ImageFilter.GaussianBlur(radius=nivel_suavidade * fator))
        mask = mask.point(lambda p: 255 if p > 128 else 0)

    # Gerar área da Linha (borda externa)
    mask_linha = mask.filter(ImageFilter.MaxFilter(tornar_impar(l_px_s if l_px_s > 0 else 1)))

    # Redimensionar máscaras de volta para o tamanho original
    mask_f = mask.resize((img.width + distancia_px*2 + 180, img.height + distancia_px*2 + 180), Image.LANCZOS)
    mask_f = mask_f.point(lambda p: 255 if p > 128 else 0)
    mask_l_f = mask_linha.resize(mask_f.size, Image.LANCZOS)
    mask_l_f = mask_l_f.point(lambda p: 255 if p > 128 else 0)

    final_rgba = Image.new("RGBA", mask_f.size, (0, 0, 0, 0))
    
    # Aplicar fundo branco (Sangria)
    if tipo_contorno == "Com Sangria":
        final_rgba.paste((255, 255, 255, 255), (0, 0), mask_f)
    
    # Aplicar Linha Preta de corte
    if linha_ativa:
        camada_preta = Image.new("RGBA", mask_f.size, (0, 0, 0, 255))
        final_rgba.paste(camada_preta, (0, 0), mask_l_f)
        # Limpa o interior para a linha não invadir o desenho
        interior_limpo = mask_f.filter(ImageFilter.MinFilter(3))
        final_rgba.paste((0,0,0,0), (0,0), interior_limpo)
    
    # Centralizar e colar imagem original por cima
    pos_x = (mask_f.width - img.width) // 2
    pos_y = (mask_f.height - img.height) // 2
    img_top = Image.new("RGBA", mask_f.size, (0, 0, 0, 0))
    img_top.paste(img, (pos_x, pos_y))
    final_rgba = Image.alpha_composite(final_rgba, img_top)

    final_bbox = final_rgba.getbbox()
    return final_rgba.crop(final_bbox), mask_f.crop(final_bbox)

# --- FUNÇÃO DE MONTAGEM AUTOMÁTICA NO A4 ---
def montar_projeto(lista_config, margem_cm, nivel_suavidade, espessura_linha):
    m_px = int(margem_cm * CM_TO_PX)
    e_px = int(0.15 * CM_TO_PX) # Espaçamento entre peças
    all_pieces = []
    
    for item in lista_config:
        img_base = item['img'].convert("RGBA")
        alvo_px = item['medida_cm'] * CM_TO_PX
        w, h = img_base.size
        # Redimensiona mantendo proporção
        img_res = img_base.resize((int(w*(alvo_px/h)), int(alvo_px)) if h>w else (int(alvo_px), int(h*(alvo_px/w))), Image.LANCZOS)
        
        pv, pm = gerar_contorno_individual(img_res, item['tipo'], item['sangria_val'], item['linha'], nivel_suavidade, espessura_linha)
        for _ in range(item['quantidade']): 
            all_pieces.append({'img': pv, 'mask': pm})

    folhas = []
    pecas_restantes = all_pieces.copy()
    
    while pecas_restantes and len(folhas) < 20:
        temp_canvas = Image.new("RGBA", (A4_WIDTH, A4_HEIGHT), (0,0,0,0))
        cx, cy, lh = m_px, m_px, 0
        ainda_cabem = []
        
        for p in pecas_restantes:
            iw, ih = p['img'].size
            if cx + iw > A4_WIDTH - m_px:
                cx, cy, lh = m_px, cy + lh + e_px, 0
            if cy + ih <= A4_HEIGHT - m_px:
                temp_canvas.paste(p['img'], (cx, cy), p['img'])
                cx, lh = cx + iw + e_px, max(lh, ih)
            else: 
                ainda_cabem.append(p)

        if temp_canvas.getbbox():
            final_page = Image.new("RGB", (A4_WIDTH, A4_HEIGHT), (255, 255, 255))
            # Centralização opcional na folha
            bbox = temp_canvas.getbbox()
            l_r, a_r = bbox[2]-bbox[0], bbox[3]-bbox[1]
            off_x, off_y = (A4_WIDTH-l_r)//2 - bbox[0], (A4_HEIGHT-a_r)//2 - bbox[1]
            final_page.paste(temp_canvas, (off_x, off_y), temp_canvas)
            folhas.append(final_page)
        pecas_restantes = ainda_cabem
        
    return folhas

# --- INTERFACE STREAMLIT ---

st.set_page_config(page_title="Bazzott Lov´s Editor", layout="wide")
st.title("✂️ Bazzott Lov´s Editor")

# CSS para melhorar a aparência
st.markdown("""
    <style>
    .stButton>button { width: 100%; border-radius: 5px; height: 3em; background-color: #FF4B4B; color: white; }
    .stDownloadButton>button { width: 100%; border-radius: 5px; height: 3em; background-color: #008000; color: white; }
    </style>
    """, unsafe_allow_html=True)

with st.sidebar:
    st.header("⚙️ 1. Ajustes Globais")
    espessura_linha = st.slider("Espessura da Linha (mm)", 0.1, 5.0, 0.3, step=0.1)
    suavidade = st.slider("Arredondamento de Cantos", 0, 30, 30)
    margem = st.slider("Margem do Papel (cm)", 0.5, 2.5, 1.0)
    
    st.divider()
    st.header("📦 2. Sincronização em Massa")
    b_size = st.number_input("Tamanho Padrão (cm)", 1.0, 25.0, 5.0)
    b_qtd = st.number_input("Quantidade Padrão", 1, 100, 1)
    
    lista_sangrias = ["2mm", "3mm", "5mm", "7mm", "9mm"]
    b_sangria = st.selectbox("Sangria Padrão", lista_sangrias, index=4) # Index 4 é 9mm
    
    if st.button("🔄 Aplicar a Todos os Itens"):
        # Itera sobre o estado da sessão para atualizar as chaves dos inputs individuais
        for key in st.session_state.keys():
            if key.startswith("m"): st.session_state[key] = b_size
            if key.startswith("q"): st.session_state[key] = b_qtd
            if key.startswith("s"): st.session_state[key] = b_sangria
        st.rerun()

    st.divider()
    if st.button("🗑️ Limpar Galeria"):
        st.session_state.clear()
        st.rerun()

# Upload de arquivos
u = st.file_uploader("Arraste seus arquivos PNG aqui", type="png", accept_multiple_files=True)

if u:
    confs = []
    # Grid para exibição dos controles das imagens
    for i, f in enumerate(u):
        with st.expander(f"Configurar: {f.name}", expanded=True):
            c1, c2, c3 = st.columns([1, 2, 2])
            img_upload = Image.open(f)
            
            with c1:
                st.image(img_upload, width=100)
            
            with c2:
                med = st.number_input(f"Altura/Largura (cm)", 1.0, 25.0, 5.0, key=f"m{i}")
                qtd = st.number_input(f"Quantidade", 1, 100, 1, key=f"q{i}")
            
            with c3:
                tipo = st.selectbox("Estilo de Corte", ["Com Sangria", "Corte no Desenho (0mm)"], key=f"t{i}")
                sang = st.selectbox("Tamanho da Sangria", lista_sangrias, index=4, key=f"s{i}")
                lin = st.checkbox("Ativar Linha Preta", True, key=f"l{i}")
                
            confs.append({
                'img': img_upload, 
                'medida_cm': med, 
                'quantidade': qtd, 
                'tipo': tipo, 
                'sangria_val': sang, 
                'linha': lin
            })

    st.divider()

    if st.button("🚀 GERAR FOLHAS PARA IMPRESSÃO"):
        with st.spinner("Organizando layout e processando bordas..."):
            folhas_finais = montar_projeto(confs, margem, suavidade, espessura_linha)
            
            if folhas_finais:
                st.success(f"Sucesso! {len(folhas_finais)} página(s) gerada(s).")
                
                # Preview das folhas
                for idx, folha in enumerate(folhas_finais):
                    st.image(folha, caption=f"Página {idx+1}", use_container_width=True)
                
                # Preparação do PDF para download
                pdf_bytes = io.BytesIO()
                folhas_finais[0].save(
                    pdf_bytes, 
                    format="PDF", 
                    save_all=True, 
                    append_images=folhas_finais[1:], 
                    resolution=300.0
                )
                
                st.download_button(
                    label="📥 Baixar PDF Final para Impressão",
                    data=pdf_bytes.getvalue(),
                    file_name="Bazzott_Lovs_Projeto.pdf",
                    mime="application/pdf"
                )
