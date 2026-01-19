import streamlit as st
from PIL import Image, ImageChops, ImageFilter, ImageDraw, ImageOps
import io
import random

# Configuração A4 300 DPI
A4_WIDTH = 2480
A4_HEIGHT = 3508
CM_TO_PX = 118.11 

def tornar_impar(n):
    n = int(n)
    if n < 1: return 1
    return n if n % 2 != 0 else n + 1

def gerar_contorno_fast(img, sangria_cm, linha_ativa):
    respiro = int(sangria_cm * CM_TO_PX * 2) + 40 if sangria_cm > 0 else 20
    img_exp = Image.new("RGBA", (img.width + respiro, img.height + respiro), (0, 0, 0, 0))
    img_exp.paste(img, (respiro // 2, respiro // 2))
    alpha = img_exp.split()[3].point(lambda p: 255 if p > 100 else 0)
    
    n_max = tornar_impar(20) 
    mask = alpha.filter(ImageFilter.MaxFilter(n_max))
    
    if sangria_cm > 0:
        sangria_px = tornar_impar(int(sangria_cm * CM_TO_PX))
        mask = mask.filter(ImageFilter.MaxFilter(sangria_px))
        mask = mask.filter(ImageFilter.GaussianBlur(6)).point(lambda p: 255 if p > 128 else 0)
    else:
        mask = alpha.filter(ImageFilter.GaussianBlur(1)).point(lambda p: 255 if p > 128 else 0)

    nova_img = Image.new("RGBA", img_exp.size, (0, 0, 0, 0))
    if linha_ativa and sangria_cm > 0:
        linha_mask = mask.filter(ImageFilter.MaxFilter(3))
        nova_img.paste((0,0,0,255), (0,0), linha_mask)
    if sangria_cm > 0:
        nova_img.paste((255,255,255,255), (0,0), mask)
    nova_img.paste(img_exp, (0,0), img_exp)
    bbox = nova_img.getbbox()
    return (nova_img.crop(bbox), mask.crop(bbox)) if bbox else (nova_img, mask)

def criar_nova_folha():
    canvas = Image.new('RGBA', (A4_WIDTH, A4_HEIGHT), (255, 255, 255, 255))
    mask = Image.new('L', (A4_WIDTH, A4_HEIGHT), 0)
    return canvas, mask

def montar_multiplas_folhas_inteligente(lista_config, margem_cm, sangria_cm, linha_ativa, permitir_90):
    m_px = int(margem_cm * CM_TO_PX)
    e_px = int(0.15 * CM_TO_PX) # Espaço fixo pequeno entre peças
    all_pieces = []
    
    # Identifica se é imagem única ou várias
    e_imagem_unica = len(lista_config) == 1

    for item in lista_config:
        img = item['img'].convert("RGBA")
        if item['espelhar']: img = ImageOps.mirror(img)
        w_px = int(item['width_cm'] * CM_TO_PX)
        img = img.resize((w_px, int(img.size[1] * (w_px/img.size[0]))), Image.Resampling.LANCZOS)
        peca, m_c = gerar_contorno_fast(img, sangria_cm, linha_ativa)
        p_90, m_90 = (peca.rotate(90, expand=True), m_c.rotate(90, expand=True)) if permitir_90 else (None, None)
        for _ in range(item['quantidade']):
            all_pieces.append({'orig': (peca, m_c), 'rot': (p_90, m_90)})

    # Ordenar por tamanho
    all_pieces.sort(key=lambda x: x['orig'][0].size[0] * x['orig'][0].size[1], reverse=True)
    
    folhas_finais = []
    pecas_restantes = all_pieces.copy()

    while pecas_restantes:
        canvas, mask_canvas = criar_nova_folha()
        nao_couberam = []

        if e_imagem_unica:
            # MODO LINHAS AUTOMÁTICO
            curr_x, curr_y, linha_h = m_px, m_px, 0
            for i, p in enumerate(pecas_restantes):
                img_p, m_p = p['orig']
                iw, ih = img_p.size
                if curr_x + iw + m_px > A4_WIDTH:
                    curr_x, curr_y = m_px, curr_y + linha_h + e_px
                    linha_h = 0
                if curr_y + ih + m_px <= A4_HEIGHT:
                    canvas.paste(img_p, (curr_x, curr_y), img_p)
                    mask_canvas.paste(m_p, (curr_x, curr_y), m_p)
                    curr_x += iw + e_px
                    linha_h = max(linha_h, ih)
                else:
                    nao_couberam = pecas_restantes[i:]
                    break
        else:
            # MODO TETRIS AUTOMÁTICO
            for p in pecas_restantes:
                encaixou = False
                opcoes = [p['orig']]
                if p['rot'][0] is not None: opcoes.append(p['rot'])
                for img_p, mask_p in opcoes:
                    iw, ih = img_p.size
                    for _ in range(1500):
                        tx = random.randint(m_px, max(m_px, A4_WIDTH - iw - m_px))
                        ty = random.randint(m_px, max(m_px, A4_HEIGHT - ih - m_px))
                        if not ImageChops.multiply(mask_canvas.crop((tx, ty, tx+iw, ty+ih)), mask_p).getbbox():
                            canvas.paste(img_p, (tx, ty), img_p)
                            mask_canvas.paste(mask_p, (tx, ty), mask_p)
                            encaixou = True
                            break
                    if encaixou: break
                if not encaixou:
                    nao_couberam.append(p)
        
        folhas_finais.append(canvas.convert("RGB"))
        pecas_restantes = nao_couberam
        if len(folhas_finais) > 20: break 

    return folhas_finais, "Linhas" if e_imagem_unica else "Tetris"

# --- INTERFACE ---
st.set_page_config(page_title="ScanNCut Smart Studio", layout="wide")

with st.sidebar:
    st.header("⚙️ Configurações")
    opcoes_sangria = {"Desligado": 0.0, "0.25 cm": 0.25, "0.50 cm": 0.50, "0.75 cm": 0.75, "1.00 cm": 1.00}
    sangria_sel = st.selectbox("Sangria", list(opcoes_sangria.keys()), index=1)
    sangria_valor = opcoes_sangria[sangria_sel]
    linha_corte = st.toggle("Linha Preta", value=True) if sangria_valor > 0 else False
    st.divider()
    st.info("💡 O sistema escolherá automaticamente entre modo 'Linhas' ou 'Tetris' baseado nos seus arquivos.")
    margem = st.slider("Margem (cm)", 0.3, 1.5, 0.5)

st.title("✂️ ScanNCut Pro: Inteligência de Layout")

uploads = st.file_uploader("Suba seus PNGs", type=['png'], accept_multiple_files=True)

if uploads:
    config_list = []
    cols = st.columns(4)
    for i, arq in enumerate(uploads):
        with cols[i % 4]:
            img_ui = Image.open(arq)
            st.image(img_ui, width=80)
            l = st.number_input(f"cm", 1.0, 25.0, 5.0, 0.1, key=f"w{i}")
            q = st.number_input(f"Qtd", 1, 100, 1, key=f"q{i}")
            m = st.checkbox("Mirror", key=f"m{i}")
            config_list.append({'img': img_ui, 'width_cm': l, 'quantidade': q, 'espelhar': m})

    if st.button("🚀 GERAR PROJETO COMPLETO (PDF)"):
        with st.spinner("Analisando e organizando..."):
            lista_folhas, modo_usado = montar_multiplas_folhas_inteligente(config_list, margem, sangria_valor, linha_corte, True)
            
            st.success(f"Modo detectado: **{modo_usado}**. Total de {len(lista_folhas)} folha(s).")
            
            for idx, f in enumerate(lista_folhas):
                st.image(f, caption=f"Página {idx+1}", use_container_width=True)
            
            buf_pdf = io.BytesIO()
            lista_folhas[0].save(buf_pdf, format="PDF", save_all=True, append_images=lista_folhas[1:], resolution=300.0)
            st.download_button("📥 Baixar PDF Multi-Páginas", buf_pdf.getvalue(), "projeto_scanncut_smart.pdf", use_container_width=True)
