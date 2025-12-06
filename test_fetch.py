"""
특허로 PDF 다운로드 전체 테스트 (pdfkit 변환 포함)
"""
import re
import pdfkit
import requests
from patent_pdf_downloader import normalize_rgst_no, parse_pdf_data, parse_additional_params
from app import build_payload

# wkhtmltopdf 설정
WKHTMLTOPDF_PATH = r'C:\Program Files\wkhtmltopdf\bin\wkhtmltopdf.exe'
pdfkit_config = pdfkit.configuration(wkhtmltopdf=WKHTMLTOPDF_PATH)

rgst_no = "10-2312907"
normalized = normalize_rgst_no(rgst_no)
print(f"등록번호: {rgst_no} -> {normalized}")

session = requests.Session()

headers = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
}

# ============================================================
# STEP 1: 등록정보 페이지에서 vRgstNo, vFeeStartAnn 추출
# ============================================================
print("\n[STEP 1] 등록정보 페이지 조회...")
url1 = f"https://www.patent.go.kr/smart/jsp/kiponet/ma/mamarkapply/infomodifypatent/ReadChgFrmRgstInfo.do?rgstNo={normalized}"
response1 = session.get(url1, headers=headers, timeout=30)
print(f"Status: {response1.status_code}, Length: {len(response1.text)}")

# ============================================================
# STEP 2: 연차등록안내서 팝업 페이지 POST 요청
# ============================================================
print("\n[STEP 2] 연차등록안내서 팝업 페이지 POST 요청...")
vRgstNo_match = re.search(r"var\s+vRgstNo\s*=\s*'([^']*)'", response1.text)
vFeeStartAnn_match = re.search(r"var\s+vFeeStartAnn\s*=\s*'([^']*)'", response1.text)
vRgstNo = vRgstNo_match.group(1) if vRgstNo_match else normalized
vFeeStartAnn = vFeeStartAnn_match.group(1) if vFeeStartAnn_match else ''

url2 = "https://www.patent.go.kr/smart/jsp/kiponet/mp/mpopenpatinfo/rgstinfo/RetrieveRgstFee.do"
response2 = session.post(url2, data={'rgstNo': vRgstNo, 'startAnn': vFeeStartAnn}, headers=headers, timeout=30)
print(f"Status: {response2.status_code}, Length: {len(response2.text)}")

# 데이터 파싱
data_list = parse_pdf_data(response2.text)
additional = parse_additional_params(response2.text)
print(f"파싱 결과: {len(data_list)}개")

if not data_list:
    print("❌ 데이터 없음")
    exit(1)

# ============================================================
# STEP 3: HTML 페이지 다운로드
# ============================================================
print("\n[STEP 3] HTML 페이지 다운로드...")
original_data_string = data_list[0]
ls_arr = original_data_string.split('#@')
payload = build_payload(ls_arr, additional)

url3 = "https://www.patent.go.kr/smart/jsp/kiponet/ma/infomodifypatent/ReadAnnualRgstFeeRes2.do"

pdf_headers = {
    'Content-Type': 'application/x-www-form-urlencoded',
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
    'Referer': 'https://www.patent.go.kr/smart/jsp/kiponet/mp/mpopenpatinfo/rgstinfo/RetrieveRgstFee.do',
}

response3 = session.post(url3, data=payload, headers=pdf_headers, timeout=60)
print(f"Status: {response3.status_code}")
print(f"Content-Length: {len(response3.content)} bytes")

# HTML 저장 및 상대 경로 -> 절대 경로 변환
html_content = response3.content.decode('utf-8')

# 상대 경로를 절대 경로로 변환
html_content = html_content.replace('src="/smart/', 'src="https://www.patent.go.kr/smart/')
html_content = html_content.replace('href="/smart/', 'href="https://www.patent.go.kr/smart/')

with open("test_response.html", "w", encoding="utf-8") as f:
    f.write(html_content)
print("HTML 저장 완료: test_response.html")

# ============================================================
# STEP 4: HTML -> PDF 변환
# ============================================================
print("\n[STEP 4] HTML -> PDF 변환 중...")
try:
    pdf_options = {
        'page-size': 'A4',
        'encoding': 'UTF-8',
        'no-outline': None,
        'quiet': '',
        'disable-javascript': None,
        'disable-external-links': None,
        'load-error-handling': 'ignore',
        'load-media-error-handling': 'ignore',
    }
    pdf_content = pdfkit.from_string(
        html_content,
        False,
        options=pdf_options,
        configuration=pdfkit_config
    )
    
    with open("test_download.pdf", "wb") as f:
        f.write(pdf_content)
    
    print(f"✅ PDF 변환 성공!")
    print(f"PDF 크기: {len(pdf_content)} bytes")
    print("저장 완료: test_download.pdf")
    
except Exception as e:
    print(f"❌ PDF 변환 실패: {e}")

