import streamlit as st
import requests
import os
import json
import base64
from PIL import Image, ImageDraw
from io import BytesIO
from datetime import datetime

# PDF 라이브러리
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Image as RLImage
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import inch
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfbase import pdfmetrics


# =====================================================
# 기본 설정
# =====================================================
st.set_page_config(page_title="현장 위험 분석 AI", layout="wide")

st.markdown("""
<style>
.title-box {
    background: linear-gradient(135deg, #ce93d8, #ab47bc);
    padding: 12px;
    border-radius: 16px;
    text-align: center;
    margin-bottom: 15px;
    box-shadow: 0px 8px 20px rgba(0,0,0,0.15);
    width: 45%;
    margin-left: auto;
    margin-right: auto;
}
.main-title {
    font-size: 30px;
    font-weight: bold;
    color: white;
}
.sub-title {
    font-size: 13px;
    color: #f3e5f5;
}
</style>

<div class="title-box">
    <div class="main-title">AI 현장 위험 분석 보고 시스템</div>
    <div class="sub-title">사진 업로드 → 자동 분석 → PDF 저장</div>
</div>
""", unsafe_allow_html=True)

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
if not OPENAI_API_KEY:
    st.error("OPENAI_API_KEY가 설정되지 않았습니다.")
    st.stop()


# =====================================================
# CSS
# =====================================================
st.markdown("""
<style>
.risk-card {
    background: linear-gradient(135deg, #ffffff, #f5f6fa);
    padding: 15px;
    margin: 12px 0;
    border-radius: 16px;
    box-shadow: 0px 6px 15px rgba(0,0,0,0.10);
    transition: transform 0.2s;
}
.risk-card:hover { transform: translateY(-3px); }

.badge {
    float: right;
    font-size: 22px;
    font-weight: 900;
    padding: 10px 15px;
    border-radius: 12px;
    color: white;
}

.risk-title {
    font-size: 20px;
    font-weight: 900;
    margin-bottom: 8px;
}

.risk-text {
    font-size: 14px;
    line-height: 1.4;
    margin-top: 6px;
    color: black;
}

.divider {
    height: 1px;
    background-color: #dcdde1;
    margin: 8px 0;
}
</style>
""", unsafe_allow_html=True)


# =====================================================
# GPT 이미지 분석
# =====================================================
def analyze_image(image_file):
    image_bytes = base64.b64encode(image_file.getvalue()).decode()
    image_data_url = f"data:image/png;base64,{image_bytes}"

    headers = {
        "Authorization": f"Bearer {OPENAI_API_KEY}",
        "Content-Type": "application/json"
    }

    payload = {
        "model": "gpt-4.1-mini",
        "input": [
            {
                "role": "user",
                "content": [
                    {"type": "input_image", "image_url": image_data_url},
                    {"type": "input_text",
                     "text": """
이 사진에서 위험한 요소를 모두 찾으세요.
위험도 점수 포함. JSON 배열만 반환.

[
  {
    "name": "위험요소명",
    "score": 0,
    "color": "빨강/노랑/초록",
    "caution": "조심할 점",
    "solution": "조치 방법",
    "box": [x1, y1, x2, y2]
  }
]
"""}
                ]
            }
        ]
    }

    response = requests.post(
        "https://api.openai.com/v1/responses",
        headers=headers,
        json=payload,
        timeout=60
    )

    if response.status_code != 200:
        st.error("OpenAI API 오류")
        st.write(response.text)
        return None

    data = response.json()
    output_text = ""
    for item in data.get("output", []):
        for content in item.get("content", []):
            if content.get("type") == "output_text":
                output_text += content.get("text", "")

    try:
        return json.loads(output_text)
    except:
        st.error("JSON 파싱 실패")
        st.write(output_text)
        return None


# =====================================================
# PDF 생성
# =====================================================
def create_pdf(results, uploaded_file, site_name):
    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer)
    elements = []

    pdfmetrics.registerFont(TTFont('Nanum', 'NanumGothic.ttf'))

    style = ParagraphStyle(
        name='Normal',
        fontName='Nanum',
        fontSize=12
    )

    elements.append(Paragraph("AI 현장 위험 분석 보고서", style))
    elements.append(Paragraph(f"작성일: {datetime.today().strftime('%Y-%m-%d')}", style))
    elements.append(Paragraph(f"국소명: {site_name}", style))
    elements.append(Spacer(1, 0.3 * inch))

    uploaded_file.seek(0)
    img = RLImage(uploaded_file)
    img.drawWidth = 5 * inch
    img.drawHeight = 2 * inch
    img.hAlign = 'LEFT'
    elements.append(img)
    elements.append(Spacer(1, 0.5 * inch))

    for r in results:
        elements.append(Paragraph(f"■ 위험요소: {r['name']}", style))
        elements.append(Paragraph(f"위험도 점수: {r['score']}", style))
        elements.append(Paragraph(f"조심할 점: {r['caution']}", style))
        elements.append(Paragraph(f"조치 방법: {r['solution']}", style))
        elements.append(Spacer(1, 0.3 * inch))

    doc.build(elements)
    buffer.seek(0)
    return buffer


# =====================================================
# UI
# =====================================================
uploaded_file = st.file_uploader("📷 사진 업로드", type=["jpg","jpeg","png"])

if uploaded_file:
    image = Image.open(uploaded_file)

    with st.spinner("AI 분석 중..."):
        results = analyze_image(uploaded_file)

    if results and isinstance(results, list):
        results.sort(key=lambda x: x["score"], reverse=True)
        draw = ImageDraw.Draw(image)

        st.markdown("### 🔴 ⚠ 사진 내 위험 영역 (정확도 불완전)")
        for r in results:
            try:
                x1, y1, x2, y2 = r["box"]
                if r["color"] == "빨강":
                    box_color = "red"
                elif r["color"] == "노랑":
                    box_color = "orange"
                else:
                    box_color = "green"
                draw.rectangle([x1, y1, x2, y2], outline=box_color, width=5)
            except:
                pass

        st.image(image, width=600)

        # 🔥 여기로 이동됨 (사진 아래)
        col_site, _ = st.columns([1, 1])  # 화면을 반으로 나눔
        with col_site:
            site_name = st.text_input("📍 국소명 입력")

        pdf_file = create_pdf(results, uploaded_file, site_name)

        col1, col2 = st.columns([8, 2])
        with col1:
            st.download_button(
                "📄 PDF 다운로드",
                data=pdf_file,
                file_name="AI_위험분석보고서.pdf",
                mime="application/pdf"
            )

        st.markdown("### 📊 위험 분석 결과")

        for r in results:
            score = r["score"]
            if r["color"] == "빨강":
                badge_color = "#d32f2f"
            elif r["color"] == "노랑":
                badge_color = "#f57c00"
            else:
                badge_color = "#2e7d32"

            st.markdown(f"""
<div class="risk-card">
    <div class="badge" style="background:{badge_color};">{score}점</div>
    <div class="risk-title" style="color:{badge_color};">{r['name']}</div>
    <div class="divider"></div>
    <div class="risk-text"><b>⚠ 조심할 점:</b> {r['caution']}</div>
    <div class="risk-text"><b>🛠 조치 방법:</b> {r['solution']}</div>
</div>
""", unsafe_allow_html=True)

    else:
        st.warning("위험요소를 찾지 못했습니다.")