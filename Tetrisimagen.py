import streamlit as st
from PIL import Image, ImageChops, ImageFilter, ImageOps, ImageDraw, ImageFont
import io
import random
import time

# --- CONFIGURAÇÕES TÉCNICAS ---
A4_WIDTH, A4_HEIGHT = 2480, 3508
CM_TO_PX = 118.11 

def tornar_impar(n):
    n = int(n)
    return n if n % 2 != 0 else n + 1

# --- FUNÇÃO DE CONTORNO COM ALTA SUAVIZAÇÃO ---
def gerar_contorno_individual(img, tipo_contorno, sangria_escolhida, linha_ativa, nivel_suavidade):
    # Remove transparências inúteis para medir o tamanho real
    bbox_original = img.getbbox()
    if bbox_original:
        img = img.crop(bbox_original)

    if tipo_contorno == "Sem Contorno":
        alpha = img.split()[3].point(lambda p: 255 if p > 100 else 0)
        return img, alpha

    # Define a espessura da sangria em pixels
    if tipo_contorno == "Corte no Desenho (0mm)":
        p_px = 6
    else:
        valor_cm = float(sangria_escolhida.replace('mm', '')) / 10
        p_px = int(valor_cm * CM_TO_PX)
    
    # Otimização: processa a suavização em escala para evitar o efeito "escadinha"
    fator = 0.5
    img_s = img.resize((int(img.width * fator), int(img.height * fator)), Image.LANCZOS)
    p_px_s = int(p_px * fator)

    respiro = p_px_s * 2 + 60
    img_exp = Image.new("RGBA", (img_s.width + respiro, img_s.height + respiro), (0, 0, 0, 0))
    img_exp.paste(img_s, (respiro // 2, respiro // 2))
    
    # Gera a máscara base
    alpha = img_exp.split()[3].point(lambda p: 255 if p > 100 else 0)
    mask = alpha.filter(ImageFilter.MaxFilter(tornar_impar(p_px_s)))
    
    # Aplica a suavização (Blur + Threshold) para arredondar os cantos
    if nivel_suavidade > 0:
        mask = mask.filter(ImageFilter.GaussianBlur(radius=nivel_suavidade * fator))
        mask = mask.point(lambda p: 255 if p > 128 else 0)

    # Redimensiona de volta para o tamanho original com alta qualidade
    mask_f = mask.resize((img.width + p_px*2 + 80, img.height + p_px*2 + 80), Image.LANCZOS)
    mask_f = mask_f.point(lambda p: 255 if p > 128 else 0)

    nova_img = Image.new("RGBA", mask_f.size, (0, 0, 0, 0))
    
    # Linha preta de corte (suavizada)
    if linha_ativa:
        borda_guia = mask_f.filter(ImageFilter.MaxFilter(5))
        nova_img.paste((0,0,0,255), (0,0), borda_guia)
    
    nova_img.paste((255,255,255,255), (0,0), mask_f)
    
    # Centraliza a imagem original sobre o contorno
    pos_x = (nova_img.width - img.width) // 2
    pos_y = (nova_img.height - img.height) // 2
    nova_img.paste(img, (pos_x, pos_y), img)
    
    final_bbox = nova_img.getbbox()
    if final_bbox:
        return nova_img.crop(final_bbox), mask_f.crop(final_bbox)
    return nova_img, mask_f

# --- LÓGICA DE MONTAGEM ---
def montar_projeto(lista_config, margem_cm, modo_layout, nivel_suavidade):
    m_px = int(margem_cm * CM_TO_PX)
    e_px = int(0.12 * CM_TO_PX)
    
    progresso = st.progress(0)
    status_text = st.empty()
    
    all_pieces = []
    
    # 1. Cache de processamento (faz o contorno apenas uma vez por imagem original)
    status_text.text("🎨 Suavizando contornos e preparando peças...")
    for i, item in enumerate(lista_config):
        img_base = item['img'].convert("RGBA")
        alvo_px = item['medida_cm'] * CM_TO_PX
        w, h = img_base.size
        
        # Redimensionamento mantendo a proporção
        if h > w:
            img_res = img_base.resize((int(w * (alvo_px / h)), int(alvo_px)), Image.LANCZOS)
        else:
            img_res = img_base.resize((int(alvo_px), int(h * (alvo_px / w))), Image.LANCZOS)
            
        peca_v, peca_m = gerar_contorno_individual(img_res, item['tipo'], item['sangria_val'], item['linha'], nivel_suavidade)
        
        for _ in range(item['quantidade']):
            all_pieces.append({'img': peca_v, 'mask': peca_m})
        
        progresso.progress(int((i + 1) / len(lista_config) * 40))

    folhas = []
    pecas_restantes = all_pieces.copy()

    # 2. Distribuição nas folhas
    status_text.text("📏 Organizando layout das páginas...")
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
        else: # MODO TETRIS OTIMIZADO
            pecas_restantes.sort(key=lambda x: x['img'].size[0] * x['img'].size[1], reverse=True)
            for p in pecas_restantes:
                iw, ih = p['img'].size
                encaixou = False
                for _ in range(300):
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
        progresso.progress(min(90, 40 + (len(folhas) * 10)))

    status_text.text("📄 Gerando PDF final...")
    progresso.progress(100)
    time.sleep(0.5)
    progresso.empty()
    status_text.empty()
    return folhas

# --- INTERFACE STREAMLIT ---
st.set_page_config(page_title="ScanNCut Studio Pro", layout="wide")

tab1, tab2 = st.tabs(["📋 Montagem de Folhas", "🎂 Editor de Topos"])

with tab1:
    st.subheader("Organizador Automático")
    with st.sidebar:
        st.header("Configurações Globais")
        suavidade = st.slider("Arredondamento (Suavizar)", 0, 30, 15, help="Elimina o aspeto quadrado do corte.")
        modo_layout = st.radio("Layout", ["Modo Linhas", "Modo Tetris"])
        margem = st.slider("Margem (cm)", 0.3, 1.0, 0.5)
        st.divider()
        st.header("Ajuste em Massa")
        b_size = st.number_input("Tamanho (cm)", 1.0, 25.0, 5.0)
        b_qtd = st.number_input("Qtd", 1, 100, 10)
        b_sang = st.selectbox("Sangria", ["3mm", "5mm", "7mm", "9mm"])
        if st.button("🪄 Sincronizar Tudo"):
            for i in range(100):
                if f"m{i}" in st.session_state:
                    st.session_state[f"m{i}"] = b_size
                    st.session_state[f"q{i}"] = b_qtd
                    st.session_state[f"s{i}"] = b_sang

    u = st.file_uploader("Upload PNGs", type="png", accept_multiple_files=True, key="montagem_u")
    if u:
        confs = []
        for i, f in enumerate(u):
            with st.expander(f"⚙️ {f.name}", expanded=False):
                c1, c2, c3 = st.columns([1, 2, 2])
                img = Image.open(f)
                with c1: st.image(img, width=80)
                with c2:
                    med = st.number_input(f"Tam (cm)", 1.0, 25.0, key=f"m{i}")
                    qtd = st.number_input(f"Qtd", 1, 100, key=f"q{i}")
                with c3:
                    tipo = st.selectbox("Corte", ["Com Sangria", "Corte no Desenho (0mm)"], key=f"t{i}")
                    sang = st.selectbox("mm", ["3mm", "5mm", "7mm", "9mm"], key=f"s{i}")
                    lin = st.checkbox("Linha Preta", value=True, key=f"l{i}")
                confs.append({'img': img, 'medida_cm': med, 'quantidade': qtd, 'tipo': tipo, 'sangria_val': sang, 'linha': lin, 'espelhar': False})

        if st.button("🚀 GERAR PROJETO"):
            folhas = montar_projeto(confs, margem, modo_layout, suavidade)
            if folhas:
                for idx, f in enumerate(folhas): st.image(f, caption=f"Página {idx+1}", use_container_width=True)
                out = io.BytesIO()
                folhas[0].save(out, format="PDF", save_all=True, append_images=folhas[1:], resolution=300.0)
                st.download_button("📥 Baixar PDF", out.getvalue(), "projeto_final.pdf", use_container_width=True)

with tab2:
    st.subheader("Criação de Nomes e Topos")
    col_ed, col_pre = st.columns([1, 1])
    
    with col_ed:
        texto_nome = st.text_input("Nome/Texto", "Parabéns")
        cor_f = st.color_picker("Cor da Letra", "#FF007F")
        sang_topo = st.selectbox("Espessura da Borda", ["3mm", "5mm", "7mm", "9mm"], index=1)
        
        st.warning("⚠️ O Editor de Topos usa fonte padrão. Em breve: suporte para fontes .ttf personalizadas.")

    with col_pre:
        # Simulação simples de texto (Canvas)
        img_t = Image.new("RGBA", (1200, 400), (0,0,0,0))
        d = ImageDraw.Draw(img_t)
        # Tenta desenhar o texto (usando fonte padrão do sistema)
        d.text((100, 100), texto_nome, fill=cor_f)
        
        # Aplica o nosso motor de contorno suave ao texto
        peca_t, _ = gerar_contorno_individual(img_t, "Com Sangria", sang_topo, True, 15)
        st.image(peca_t, caption="Prévia do Topo Suavizado")
        
        st.info("Para usar este nome, salve a imagem e suba-a na aba de Montagem.")
