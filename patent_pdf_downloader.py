"""
특허로 연차등록안내서 PDF 다운로드 자동화 스크립트
- Selenium 없이 requests 모듈만 사용
- printAnnualRgstFeeForm3 함수의 47개 파라미터 재현

사용법:
    python patent_pdf_downloader.py 1023129070000
    또는
    python patent_pdf_downloader.py 10-2312907-00-00
"""

import re
import sys
import requests
from typing import Optional, Tuple


# ============================================================
# 상수 정의
# ============================================================
BASE_URL = 'https://www.patent.go.kr'

# 등록정보 조회 페이지 URL (1단계)
RGST_INFO_URL = '/smart/jsp/kiponet/ma/mamarkapply/infomodifypatent/ReadChgFrmRgstInfo.do'

# 출원정보 조회 페이지 URL (출원번호 -> 등록번호 변환용)
APPL_INFO_URL = '/smart/jsp/kiponet/ma/mamarkapply/infomodifypatent/ReadChgFrmApplInfo.do'

# 연차등록안내서 팝업 페이지 URL (2단계)
RGST_FEE_POPUP_URL = '/smart/jsp/kiponet/mp/mpopenpatinfo/rgstinfo/RetrieveRgstFee.do'

# PDF 다운로드 URL
PDF_DOWNLOAD_URL = '/smart/jsp/kiponet/ma/infomodifypatent/ReadAnnualRgstFeeRes2.do'
PDF_DOWNLOAD_URL_TRADEMARK = '/smart/jsp/kiponet/ma/infomodifypatent/ReadAnnualRgstFeeRes4.do'


def normalize_rgst_no(rgst_no: str) -> str:
    """
    등록번호를 정규화합니다.
    
    입력 형식:
        - '1023129070000' → '1023129070000'
        - '10-2312907-00-00' → '1023129070000'
        - '10-2312907' → '1023129070000' (뒤 0000 자동 추가)
    """
    # 하이픈 제거
    normalized = rgst_no.replace('-', '')
    
    # 뒤 4자리가 없으면 '0000' 추가
    if len(normalized) == 9:  # 예: 102312907
        normalized += '0000'
    elif len(normalized) == 10:  # 예: 1023129070
        normalized += '000'
        
    return normalized


def normalize_appl_no(appl_no: str) -> str:
    """
    출원번호를 정규화합니다.
    
    입력 형식:
        - '10-2020-0012345' → '1020200012345'
        - '1020200012345' → '1020200012345'
    """
    # 하이픈 제거
    return appl_no.replace('-', '')


def is_application_number(number: str) -> bool:
    """
    출원번호인지 등록번호인지 구분합니다.
    
    출원번호: 13자리 (예: 1020200012345)
    등록번호: 13자리 (예: 1023129070000)
    
    구분 기준: 출원번호는 연도 정보가 포함 (4~7번째 자리가 연도)
    """
    normalized = number.replace('-', '')
    
    # 출원번호 형식: XX-YYYY-XXXXXXX 또는 XXYYYYXXXXXXX
    # 4~7번째 자리가 연도 (2000~2099 범위)
    if len(normalized) >= 13:
        year_part = normalized[2:6]
        if year_part.isdigit():
            year = int(year_part)
            # 2000년대 연도면 출원번호로 판단
            if 2000 <= year <= 2099:
                return True
    
    return False


def format_display_number(normalized: str) -> str:
    """
    정규화된 번호를 표시용 형식으로 변환합니다.
    
    등록번호: 1023129070000 → 10-2312907
    출원번호: 1020200012345 → 10-2020-0012345
    """
    if is_application_number(normalized):
        # 출원번호: XX-YYYY-XXXXXXX
        return f"{normalized[:2]}-{normalized[2:6]}-{normalized[6:]}"
    else:
        # 등록번호: XX-XXXXXXX (뒤 0000 제외)
        return f"{normalized[:2]}-{normalized[2:9]}"


def get_rgst_no_from_appl_no(session: requests.Session, appl_no: str) -> Optional[str]:
    """
    출원번호로 등록번호를 조회합니다.
    
    Args:
        session: requests.Session 객체
        appl_no: 정규화된 출원번호 (예: '1020190065700')
        
    Returns:
        등록번호 (예: '1023061440000') 또는 None (등록되지 않은 경우)
    """
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
        'Accept-Language': 'ko-KR,ko;q=0.9,en-US;q=0.8,en;q=0.7',
        'Referer': BASE_URL,
    }
    
    url = BASE_URL + APPL_INFO_URL
    params = {'applNo': appl_no}
    
    try:
        response = session.get(url, params=params, headers=headers, timeout=30)
        response.raise_for_status()
        
        # HTML에서 등록번호 추출
        # 패턴: 10-2306144-00-00 또는 1023061440000
        # "등록번호" 근처에서 찾기
        rgst_pattern = r'등록번호[^0-9]*(\d{2}-\d{7}-\d{2}-\d{2}|\d{13})'
        match = re.search(rgst_pattern, response.text)
        
        if match:
            rgst_no = match.group(1)
            return normalize_rgst_no(rgst_no)
        
        # 대안: vRgstNo 변수에서 찾기
        vRgstNo_match = re.search(r"var\s+vRgstNo\s*=\s*'([^']*)'", response.text)
        if vRgstNo_match and vRgstNo_match.group(1):
            return normalize_rgst_no(vRgstNo_match.group(1))
        
        # 대안: rgstNo 파라미터에서 찾기
        rgstNo_match = re.search(r"rgstNo['\"]?\s*[:=]\s*['\"]?(\d{13})['\"]?", response.text)
        if rgstNo_match:
            return rgstNo_match.group(1)
            
        return None
        
    except requests.RequestException as e:
        print(f"출원정보 조회 실패: {e}")
        return None


def get_registration_page(session: requests.Session, rgst_no: str) -> str:
    """
    연차등록안내서 팝업 페이지 HTML을 가져옵니다. (2단계 요청)
    
    1단계: 등록정보 페이지에서 vRgstNo, vFeeStartAnn 추출
    2단계: 팝업 페이지에 POST 요청하여 ls_arg 데이터 가져오기
    
    Args:
        session: requests.Session 객체
        rgst_no: 정규화된 등록번호 (예: '1023129070000')
        
    Returns:
        팝업 페이지 HTML 소스 (ls_arg 데이터 포함)
    """
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
        'Accept-Language': 'ko-KR,ko;q=0.9,en-US;q=0.8,en;q=0.7',
        'Referer': BASE_URL,
    }
    
    # ============================================================
    # STEP 1: 등록정보 페이지에서 vRgstNo, vFeeStartAnn 추출
    # ============================================================
    url1 = BASE_URL + RGST_INFO_URL
    params = {'rgstNo': rgst_no}
    
    response1 = session.get(url1, params=params, headers=headers, timeout=30)
    response1.raise_for_status()
    
    # vRgstNo, vFeeStartAnn 파싱
    vRgstNo_match = re.search(r"var\s+vRgstNo\s*=\s*'([^']*)'", response1.text)
    vFeeStartAnn_match = re.search(r"var\s+vFeeStartAnn\s*=\s*'([^']*)'", response1.text)
    
    vRgstNo = vRgstNo_match.group(1) if vRgstNo_match else rgst_no
    vFeeStartAnn = vFeeStartAnn_match.group(1) if vFeeStartAnn_match else ''
    
    # ============================================================
    # STEP 2: 연차등록안내서 팝업 페이지 POST 요청
    # ============================================================
    url2 = BASE_URL + RGST_FEE_POPUP_URL
    data = {
        'rgstNo': vRgstNo,
        'startAnn': vFeeStartAnn,
    }
    
    response2 = session.post(url2, data=data, headers=headers, timeout=30)
    response2.raise_for_status()
    
    return response2.text


def parse_pdf_data(source_html: str) -> list[str]:
    """
    HTML에서 #@로 구분된 47개 파라미터의 원본 문자열 목록을 추출합니다.
    
    Args:
        source_html: 특허로 페이지의 HTML 소스
        
    Returns:
        각 knx 인덱스별 원본 데이터 문자열 리스트 (ls_arg[0], ls_arg[1], ...)
    
    예시 반환값:
        ["#@추납(NEW)#@0131-2-5-2025-...#@...", ...]
    """
    # ls_arg[숫자] = '...' 패턴을 찾음
    # JavaScript에서는 여러 줄에 걸쳐 + "#@" + '값' 형태로 연결됨
    
    # 정규식으로 ls_arg[n] = '...' 블록 전체 추출
    # 패턴: ls_arg[숫자] = '' 로 시작해서 다음 ls_arg 또는 세미콜론까지
    pattern = r"ls_arg\[(\d+)\]\s*=\s*''\s*((?:\s*\+\s*\"#@\"\s*\+\s*'[^']*')*)"
    
    matches = re.findall(pattern, source_html, re.DOTALL)
    
    result = []
    for idx_str, data_block in matches:
        # + "#@" + '값' 패턴에서 값들만 추출
        value_pattern = r"\+\s*\"#@\"\s*\+\s*'([^']*)'"
        values = re.findall(value_pattern, data_block)
        
        # #@로 구분된 원본 문자열 재구성 (첫 번째 빈 문자열 포함)
        original_string = '' + '#@' + '#@'.join(values)
        result.append(original_string)
    
    return result


def parse_additional_params(source_html: str) -> dict:
    """
    HTML에서 arg44, arg45, arg46에 해당하는 하드코딩된 값들을 추출합니다.
    
    Args:
        source_html: 특허로 페이지의 HTML 소스
        
    Returns:
        {'arg44': 연차, 'arg45': 발명명칭, 'arg46': 빈문자열} 딕셔너리
    """
    result = {
        'arg44': '',
        'arg45': '',
        'arg46': ''
    }
    
    # popupForm.arg44.value = '05'; 형태에서 추출
    arg44_match = re.search(r"popupForm\.arg44\.value\s*=\s*'([^']*)'\s*;", source_html)
    if arg44_match:
        result['arg44'] = arg44_match.group(1)
    
    # popupForm.arg45.value = '발명명칭'; 형태에서 추출
    arg45_match = re.search(r"popupForm\.arg45\.value\s*=\s*'([^']*)'\s*;", source_html)
    if arg45_match:
        result['arg45'] = arg45_match.group(1)
    
    # popupForm.arg46.value = ''; 형태에서 추출
    arg46_match = re.search(r"popupForm\.arg46\.value\s*=\s*'([^']*)'\s*;", source_html)
    if arg46_match:
        result['arg46'] = arg46_match.group(1)
    
    return result


def download_annual_rgst_pdf(
    session: requests.Session,
    original_data_string: str,
    output_filename: str,
    arg44: str = '',
    arg45: str = '',
    arg46: str = '',
    base_url: str = 'https://www.patent.go.kr'
) -> bool:
    """
    연차등록안내서 PDF를 다운로드합니다.
    
    Args:
        session: 로그인된 requests.Session 객체
        original_data_string: #@로 구분된 원본 데이터 문자열
        output_filename: 저장할 PDF 파일명
        arg44: 연차 (예: '05')
        arg45: 발명의 명칭
        arg46: 추가 파라미터 (보통 빈 문자열)
        base_url: 특허로 기본 URL
        
    Returns:
        성공 여부 (True/False)
    """
    # 원본 문자열을 #@로 분리하여 배열 생성
    ls_arr = original_data_string.split('#@')
    
    # ========================================
    # arg1 ~ arg47 정확한 매핑 (JavaScript 코드 기반)
    # ========================================
    # 
    # JavaScript 원본:
    #   popupForm.arg1.value  = ls_arr[0]   // 빈 문자열
    #   popupForm.arg2.value  = ls_arr[1]   // 납부유형 (예: '추납(NEW)')
    #   popupForm.arg3.value  = ls_arr[2]   // 납부번호
    #   popupForm.arg4.value  = ls_arr[3]   // 등록번호
    #   popupForm.arg5.value  = ls_arr[4]   // 납부금액
    #   popupForm.arg6.value  = ls_arr[5]   // 납부기한
    #   popupForm.arg7.value  = ls_arr[6]   // 권리자명
    #   popupForm.arg8.value  = ls_arr[7]   // 특허 제XXXXXXX호
    #   popupForm.arg9.value  = ls_arr[8]   // (빈 문자열)
    #   popupForm.arg10.value = ls_arr[9]   // 납부기한2
    #   popupForm.arg11.value = ls_arr[10]  // 연차
    #   popupForm.arg12.value = ls_arr[11]  // (빈 문자열)
    #   popupForm.arg13.value = ls_arr[12]  // 감면 안내 메시지
    #   popupForm.arg14.value = ls_arr[13]  // 감면유형
    #   popupForm.arg15.value = ls_arr[14]  // 존속기간
    #   popupForm.arg16.value = ls_arr[15]  // 기본료
    #   popupForm.arg17.value = ls_arr[16]  // 가산료
    #   popupForm.arg18.value = ls_arr[17]  // 청구항료
    #   popupForm.arg19.value = ls_arr[18]  // 청구항 수
    #   popupForm.arg20.value = ls_arr[19]  // 1차 추납기한
    #   popupForm.arg21.value = ls_arr[20]  // 2차 추납기한
    #   popupForm.arg22.value = ls_arr[21]  // 3차 추납기한
    #   popupForm.arg23.value = ls_arr[22]  // 1차 추납금액
    #   popupForm.arg24.value = ls_arr[23]  // 2차 추납금액
    #   popupForm.arg25.value = ls_arr[24]  // 3차 추납금액
    #   popupForm.arg26.value = ls_arr[25]  // (빈 문자열)
    #   popupForm.arg27.value = ls_arr[26]  // 1차 추가금
    #   popupForm.arg28.value = ls_arr[27]  // 2차 추가금
    #   popupForm.arg29.value = ls_arr[28]  // 3차 추가금
    #   popupForm.arg30.value = ls_arr[29]  // 안내서 발급일
    #   popupForm.arg31.value = ls_arr[30]  // 납부기한일
    #   popupForm.arg32.value = ls_arr[31]  // 존속기간 만료일
    #   popupForm.arg33.value = ls_arr[32]  // 가상계좌번호
    #   popupForm.arg34.value = ls_arr[33]  // 등록일
    #   popupForm.arg35.value = ls_arr[34]  // 회복기한
    #   popupForm.arg36.value = ls_arr[35]  // 회복료
    #   popupForm.arg37.value = ls_arr[36]  // 4차 추납기한
    #   popupForm.arg38.value = ls_arr[37]  // 5차 추납기한
    #   popupForm.arg39.value = ls_arr[38]  // 6차 추납기한
    #   popupForm.arg40.value = ls_arr[39]  // 4차 추납금액
    #   popupForm.arg41.value = ls_arr[40]  // 5차 추납금액
    #   popupForm.arg42.value = ls_arr[41]  // 6차 추납금액
    #   popupForm.arg43.value = ls_arr[42]  // (빈 문자열)
    #   popupForm.arg44.value = '05'        // 하드코딩 - 시작연차
    #   popupForm.arg45.value = '발명명칭'  // 하드코딩 - 발명의 명칭
    #   popupForm.arg46.value = ''          // 하드코딩 - 빈 문자열
    #   popupForm.arg47.value = ls_arr[44]  // 출원번호 (ls_arr[43] 건너뜀!)
    # ========================================
    
    payload = {
        'arg1':  ls_arr[0] if len(ls_arr) > 0 else '',
        'arg2':  ls_arr[1] if len(ls_arr) > 1 else '',
        'arg3':  ls_arr[2] if len(ls_arr) > 2 else '',
        'arg4':  ls_arr[3] if len(ls_arr) > 3 else '',
        'arg5':  ls_arr[4] if len(ls_arr) > 4 else '',
        'arg6':  ls_arr[5] if len(ls_arr) > 5 else '',
        'arg7':  ls_arr[6] if len(ls_arr) > 6 else '',
        'arg8':  ls_arr[7] if len(ls_arr) > 7 else '',
        'arg9':  ls_arr[8] if len(ls_arr) > 8 else '',
        'arg10': ls_arr[9] if len(ls_arr) > 9 else '',
        'arg11': ls_arr[10] if len(ls_arr) > 10 else '',
        'arg12': ls_arr[11] if len(ls_arr) > 11 else '',
        'arg13': ls_arr[12] if len(ls_arr) > 12 else '',
        'arg14': ls_arr[13] if len(ls_arr) > 13 else '',
        'arg15': ls_arr[14] if len(ls_arr) > 14 else '',
        'arg16': ls_arr[15] if len(ls_arr) > 15 else '',
        'arg17': ls_arr[16] if len(ls_arr) > 16 else '',
        'arg18': ls_arr[17] if len(ls_arr) > 17 else '',
        'arg19': ls_arr[18] if len(ls_arr) > 18 else '',
        'arg20': ls_arr[19] if len(ls_arr) > 19 else '',
        'arg21': ls_arr[20] if len(ls_arr) > 20 else '',
        'arg22': ls_arr[21] if len(ls_arr) > 21 else '',
        'arg23': ls_arr[22] if len(ls_arr) > 22 else '',
        'arg24': ls_arr[23] if len(ls_arr) > 23 else '',
        'arg25': ls_arr[24] if len(ls_arr) > 24 else '',
        'arg26': ls_arr[25] if len(ls_arr) > 25 else '',
        'arg27': ls_arr[26] if len(ls_arr) > 26 else '',
        'arg28': ls_arr[27] if len(ls_arr) > 27 else '',
        'arg29': ls_arr[28] if len(ls_arr) > 28 else '',
        'arg30': ls_arr[29] if len(ls_arr) > 29 else '',
        'arg31': ls_arr[30] if len(ls_arr) > 30 else '',
        'arg32': ls_arr[31] if len(ls_arr) > 31 else '',
        'arg33': ls_arr[32] if len(ls_arr) > 32 else '',
        'arg34': ls_arr[33] if len(ls_arr) > 33 else '',
        'arg35': ls_arr[34] if len(ls_arr) > 34 else '',
        'arg36': ls_arr[35] if len(ls_arr) > 35 else '',
        'arg37': ls_arr[36] if len(ls_arr) > 36 else '',
        'arg38': ls_arr[37] if len(ls_arr) > 37 else '',
        'arg39': ls_arr[38] if len(ls_arr) > 38 else '',
        'arg40': ls_arr[39] if len(ls_arr) > 39 else '',
        'arg41': ls_arr[40] if len(ls_arr) > 40 else '',
        'arg42': ls_arr[41] if len(ls_arr) > 41 else '',
        'arg43': ls_arr[42] if len(ls_arr) > 42 else '',
        'arg44': arg44,  # 하드코딩 - 시작연차
        'arg45': arg45,  # 하드코딩 - 발명의 명칭
        'arg46': arg46,  # 하드코딩 - 빈 문자열
        'arg47': ls_arr[44] if len(ls_arr) > 44 else '',  # 주의: ls_arr[43] 건너뜀!
    }
    
    # URL 결정 (등록번호 첫 자리가 '4'면 상표용 URL 사용)
    rgst_no = payload.get('arg4', '')
    if rgst_no.startswith('4'):
        url_path = '/smart/jsp/kiponet/ma/infomodifypatent/ReadAnnualRgstFeeRes4.do'
    else:
        url_path = '/smart/jsp/kiponet/ma/infomodifypatent/ReadAnnualRgstFeeRes2.do'
    
    full_url = base_url + url_path
    
    # POST 요청 전송
    headers = {
        'Content-Type': 'application/x-www-form-urlencoded',
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
        'Accept': 'application/pdf,*/*',
    }
    
    try:
        response = session.post(full_url, data=payload, headers=headers, timeout=60)
        response.raise_for_status()
        
        # PDF 응답인지 확인
        content_type = response.headers.get('Content-Type', '')
        if 'pdf' not in content_type.lower() and not response.content.startswith(b'%PDF'):
            print(f"경고: 응답이 PDF가 아닐 수 있습니다. Content-Type: {content_type}")
        
        # 바이너리 파일로 저장
        with open(output_filename, 'wb') as f:
            f.write(response.content)
        
        print(f"PDF 저장 완료: {output_filename} ({len(response.content):,} bytes)")
        return True
        
    except requests.RequestException as e:
        print(f"PDF 다운로드 실패: {e}")
        return False


def download_by_rgst_no(
    rgst_no: str,
    output_filename: Optional[str] = None,
    knx: int = 0
) -> bool:
    """
    등록번호만으로 연차등록안내서 PDF를 다운로드합니다.
    
    Args:
        rgst_no: 등록번호 (예: '1023129070000' 또는 '10-2312907-00-00')
        output_filename: 저장할 파일명 (기본값: '연차등록안내서_{등록번호}.pdf')
        knx: 다운로드할 안내서 인덱스 (기본값: 0, 첫 번째)
        
    Returns:
        성공 여부 (True/False)
    """
    # 등록번호 정규화
    normalized_rgst_no = normalize_rgst_no(rgst_no)
    print(f"[1/4] 등록번호 정규화: {rgst_no} -> {normalized_rgst_no}")
    
    # 세션 생성
    session = requests.Session()
    
    # 등록정보 페이지 가져오기
    print(f"[2/4] 등록정보 페이지 조회 중...")
    try:
        html_source = get_registration_page(session, normalized_rgst_no)
    except requests.RequestException as e:
        print(f"ERROR: 등록정보 페이지 조회 실패 - {e}")
        return False
    
    # 데이터 파싱
    print(f"[3/4] PDF 데이터 파싱 중...")
    data_list = parse_pdf_data(html_source)
    
    if not data_list:
        print("ERROR: PDF 데이터를 찾을 수 없습니다.")
        print("       - 해당 등록번호에 연차등록안내서가 없거나")
        print("       - 로그인이 필요할 수 있습니다.")
        return False
    
    if knx >= len(data_list):
        print(f"ERROR: 인덱스 {knx}에 해당하는 데이터가 없습니다. (총 {len(data_list)}개)")
        return False
    
    # 추가 파라미터 파싱 (arg44, arg45, arg46)
    additional_params = parse_additional_params(html_source)
    
    # 파일명 설정: 출원번호 우선 사용, 없으면 등록번호 사용
    if output_filename is None:
        # PDF 데이터에서 출원번호 추출 (arg47)
        if data_list:
            original_data_string = data_list[knx]
            ls_arr = original_data_string.split('#@')
            appl_no = ls_arr[44] if len(ls_arr) > 44 else ''
            
            if appl_no and is_application_number(appl_no):
                # 출원번호가 있으면 출원번호로 파일명 생성
                normalized_appl = normalize_appl_no(appl_no)
                display_appl = format_display_number(normalized_appl)
                output_filename = f"연차등록안내서_{display_appl}.pdf"
            else:
                # 출원번호가 없으면 등록번호로 파일명 생성
                display_rgst = format_display_number(normalized_rgst_no)
                output_filename = f"연차등록안내서_{display_rgst}.pdf"
        else:
            display_rgst = format_display_number(normalized_rgst_no)
            output_filename = f"연차등록안내서_{display_rgst}.pdf"
    
    # PDF 다운로드
    print(f"[4/4] PDF 다운로드 중...")
    success = download_annual_rgst_pdf(
        session=session,
        original_data_string=data_list[knx],
        output_filename=output_filename,
        arg44=additional_params['arg44'],
        arg45=additional_params['arg45'],
        arg46=additional_params['arg46'],
    )
    
    return success


# ============================================================
# 메인 실행
# ============================================================
if __name__ == '__main__':
    """
    사용법:
        python patent_pdf_downloader.py 1023129070000
        python patent_pdf_downloader.py 10-2312907-00-00
        python patent_pdf_downloader.py 10-2312907
    """
    
    if len(sys.argv) < 2:
        print("=" * 60)
        print("특허로 연차등록안내서 PDF 다운로더")
        print("=" * 60)
        print()
        print("사용법:")
        print("  python patent_pdf_downloader.py <등록번호>")
        print()
        print("예시:")
        print("  python patent_pdf_downloader.py 1023129070000")
        print("  python patent_pdf_downloader.py 10-2312907-00-00")
        print("  python patent_pdf_downloader.py 10-2312907")
        print()
        print("참고: 등록번호 뒤 0000은 자동으로 추가됩니다.")
        sys.exit(1)
    
    rgst_no = sys.argv[1]
    output_file = sys.argv[2] if len(sys.argv) > 2 else None
    
    print("=" * 60)
    print("특허로 연차등록안내서 PDF 다운로더")
    print("=" * 60)
    print()
    
    success = download_by_rgst_no(rgst_no, output_file)
    
    if success:
        print()
        print("다운로드 완료!")
    else:
        print()
        print("다운로드 실패!")
        sys.exit(1)

