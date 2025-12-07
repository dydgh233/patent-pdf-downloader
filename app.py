"""
특허로 연차등록안내서 PDF 다운로드 웹 서버
Flask 기반 웹 애플리케이션
"""

import os
import io
import zipfile
import pdfkit
from datetime import datetime
from urllib.parse import quote
from flask import Flask, render_template, request, jsonify, send_file, Response

# wkhtmltopdf 경로 설정 (OS에 따라 자동 감지)
import platform
import shutil

def find_wkhtmltopdf():
    """wkhtmltopdf 실행 파일 경로 찾기"""
    if platform.system() == 'Windows':
        return r'C:\Program Files\wkhtmltopdf\bin\wkhtmltopdf.exe'
    
    # Linux: 여러 가능한 경로 시도
    possible_paths = [
        '/usr/local/bin/wkhtmltopdf',
        '/usr/bin/wkhtmltopdf',
        '/bin/wkhtmltopdf',
    ]
    
    # shutil.which로 PATH에서 찾기
    which_path = shutil.which('wkhtmltopdf')
    if which_path:
        return which_path
    
    # 가능한 경로에서 찾기
    for path in possible_paths:
        if os.path.exists(path):
            return path
    
    # 기본값 반환
    return '/usr/local/bin/wkhtmltopdf'

WKHTMLTOPDF_PATH = find_wkhtmltopdf()
pdfkit_config = pdfkit.configuration(wkhtmltopdf=WKHTMLTOPDF_PATH)
from patent_pdf_downloader import (
    normalize_rgst_no,
    normalize_appl_no,
    is_application_number,
    format_display_number,
    get_rgst_no_from_appl_no,
    get_registration_page,
    parse_pdf_data,
    parse_additional_params,
    download_annual_rgst_pdf,
)
import requests

app = Flask(__name__)
app.config['JSON_AS_ASCII'] = False  # 한글 JSON 지원


@app.route('/')
def index():
    """메인 페이지"""
    return render_template('index.html')


@app.route('/api/check', methods=['POST'])
def check_registration():
    """
    등록번호 또는 출원번호 유효성 검사 및 안내서 정보 조회
    """
    data = request.get_json()
    input_no = data.get('rgst_no', '').strip()
    
    if not input_no:
        return jsonify({'success': False, 'error': '등록번호 또는 출원번호를 입력해주세요.'})
    
    try:
        session = requests.Session()
        
        # 출원번호인지 등록번호인지 확인
        normalized_input = input_no.replace('-', '')
        
        if is_application_number(normalized_input):
            # 출원번호인 경우 -> 등록번호 조회
            appl_no = normalize_appl_no(input_no)
            rgst_no = get_rgst_no_from_appl_no(session, appl_no)
            
            if not rgst_no:
                return jsonify({
                    'success': False,
                    'error': '해당 출원번호의 등록정보를 찾을 수 없습니다. (미등록 또는 존재하지 않는 출원번호)'
                })
            
            normalized = rgst_no
            input_type = 'application'
        else:
            # 등록번호인 경우
            normalized = normalize_rgst_no(input_no)
            input_type = 'registration'
        
        html_source = get_registration_page(session, normalized)
        
        data_list = parse_pdf_data(html_source)
        additional = parse_additional_params(html_source)
        
        if not data_list:
            return jsonify({
                'success': False,
                'error': '연차등록안내서를 찾을 수 없습니다. (로그인 필요 또는 해당 데이터 없음)'
            })
        
        # 표시용 번호 형식
        display_no = format_display_number(normalized)
        
        return jsonify({
            'success': True,
            'rgst_no': normalized,
            'display_no': display_no,
            'input_type': input_type,
            'count': len(data_list),
            'title': additional.get('arg45', ''),
            'year': additional.get('arg44', ''),
        })
        
    except requests.RequestException as e:
        return jsonify({'success': False, 'error': f'서버 연결 실패: {str(e)}'})
    except Exception as e:
        return jsonify({'success': False, 'error': f'오류 발생: {str(e)}'})


@app.route('/api/download', methods=['POST'])
def download_pdf():
    """
    단일 PDF 다운로드
    """
    data = request.get_json()
    input_no = data.get('rgst_no', '').strip()
    knx = data.get('knx', 0)
    
    if not input_no:
        return jsonify({'success': False, 'error': '등록번호 또는 출원번호를 입력해주세요.'})
    
    try:
        session = requests.Session()
        
        # 출원번호인지 등록번호인지 확인
        normalized_input = input_no.replace('-', '')
        
        if is_application_number(normalized_input):
            # 출원번호인 경우 -> 등록번호 조회
            appl_no = normalize_appl_no(input_no)
            rgst_no = get_rgst_no_from_appl_no(session, appl_no)
            
            if not rgst_no:
                return jsonify({'success': False, 'error': '해당 출원번호의 등록정보를 찾을 수 없습니다.'})
            
            normalized = rgst_no
        else:
            normalized = normalize_rgst_no(input_no)
        
        html_source = get_registration_page(session, normalized)
        
        data_list = parse_pdf_data(html_source)
        additional = parse_additional_params(html_source)
        
        if not data_list:
            return jsonify({'success': False, 'error': '연차등록안내서를 찾을 수 없습니다.'})
        
        if knx >= len(data_list):
            return jsonify({'success': False, 'error': f'인덱스 {knx}에 해당하는 데이터가 없습니다.'})
        
        # PDF 데이터 가져오기
        original_data_string = data_list[knx]
        ls_arr = original_data_string.split('#@')
        
        payload = build_payload(ls_arr, additional)
        
        # URL 결정
        rgst_no_value = payload.get('arg4', '')
        if rgst_no_value.startswith('4'):
            url_path = '/smart/jsp/kiponet/ma/infomodifypatent/ReadAnnualRgstFeeRes4.do'
        else:
            url_path = '/smart/jsp/kiponet/ma/infomodifypatent/ReadAnnualRgstFeeRes2.do'
        
        full_url = 'https://www.patent.go.kr' + url_path
        
        headers = {
            'Content-Type': 'application/x-www-form-urlencoded',
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
            'Accept': 'application/pdf,*/*',
        }
        
        response = session.post(full_url, data=payload, headers=headers, timeout=60)
        response.raise_for_status()
        
        # HTML을 PDF로 변환
        # 파일명: 1023129070000 -> 10-2312907 (format_display_number 사용)
        display_no = format_display_number(normalized)
        filename = f"{display_no}.pdf"
        encoded_filename = quote(filename)
        
        try:
            # HTML 상대 경로 -> 절대 경로 변환
            html_content = response.content.decode('utf-8')
            html_content = html_content.replace('src="/smart/', 'src="https://www.patent.go.kr/smart/')
            html_content = html_content.replace('href="/smart/', 'href="https://www.patent.go.kr/smart/')
            
            # HTML -> PDF 변환
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
                False,  # False = 메모리에 저장
                options=pdf_options,
                configuration=pdfkit_config
            )
            
            return Response(
                pdf_content,
                mimetype='application/pdf',
                headers={
                    'Content-Disposition': f"attachment; filename*=UTF-8''{encoded_filename}"
                }
            )
        except Exception as e:
            return jsonify({'success': False, 'error': f'PDF 변환 실패: {str(e)}'})
        
    except requests.RequestException as e:
        return jsonify({'success': False, 'error': f'다운로드 실패: {str(e)}'})
    except Exception as e:
        return jsonify({'success': False, 'error': f'오류 발생: {str(e)}'})


@app.route('/api/download-batch', methods=['POST'])
def download_batch():
    """
    여러 등록번호의 PDF를 ZIP으로 묶어서 다운로드
    """
    data = request.get_json()
    rgst_numbers = data.get('rgst_numbers', [])
    
    if not rgst_numbers:
        return jsonify({'success': False, 'error': '등록번호 목록이 비어있습니다.'})
    
    # ZIP 파일 생성
    zip_buffer = io.BytesIO()
    
    results = []
    with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zip_file:
        for input_no in rgst_numbers:
            input_no = str(input_no).strip() if input_no else ''
            if not input_no:
                continue
                
            try:
                session = requests.Session()
                
                # 출원번호인지 등록번호인지 확인
                normalized_input = input_no.replace('-', '')
                
                if is_application_number(normalized_input):
                    appl_no = normalize_appl_no(input_no)
                    rgst_no = get_rgst_no_from_appl_no(session, appl_no)
                    if not rgst_no:
                        results.append({'rgst_no': input_no, 'success': False, 'error': '등록정보 없음'})
                        continue
                    normalized = rgst_no
                else:
                    normalized = normalize_rgst_no(input_no)
                
                html_source = get_registration_page(session, normalized)
                
                data_list = parse_pdf_data(html_source)
                additional = parse_additional_params(html_source)
                
                if not data_list:
                    results.append({'rgst_no': input_no, 'success': False, 'error': '데이터 없음'})
                    continue
                
                # PDF 데이터 가져오기
                original_data_string = data_list[0]
                ls_arr = original_data_string.split('#@')
                
                payload = build_payload(ls_arr, additional)
                
                # URL 결정
                rgst_no_value = payload.get('arg4', '')
                if rgst_no_value.startswith('4'):
                    url_path = '/smart/jsp/kiponet/ma/infomodifypatent/ReadAnnualRgstFeeRes4.do'
                else:
                    url_path = '/smart/jsp/kiponet/ma/infomodifypatent/ReadAnnualRgstFeeRes2.do'
                
                full_url = 'https://www.patent.go.kr' + url_path
                
                headers = {
                    'Content-Type': 'application/x-www-form-urlencoded',
                    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
                    'Accept': 'application/pdf,*/*',
                }
                
                response = session.post(full_url, data=payload, headers=headers, timeout=60)
                response.raise_for_status()
                
                # HTML -> PDF 변환 후 ZIP에 추가
                # 파일명: 10-2312907 형식 (format_display_number 사용)
                display_no = format_display_number(normalized)
                filename = f"{display_no}.pdf"
                
                try:
                    # HTML 상대 경로 -> 절대 경로 변환
                    html_content = response.content.decode('utf-8')
                    html_content = html_content.replace('src="/smart/', 'src="https://www.patent.go.kr/smart/')
                    html_content = html_content.replace('href="/smart/', 'href="https://www.patent.go.kr/smart/')
                    
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
                    zip_file.writestr(filename, pdf_content)
                except Exception as e:
                    # PDF 변환 실패 시 HTML로 저장
                    zip_file.writestr(f"{display_no}.html", response.content)
                
                results.append({
                    'rgst_no': input_no,
                    'success': True,
                    'title': additional.get('arg45', '')
                })
                
            except Exception as e:
                results.append({'rgst_no': input_no, 'success': False, 'error': str(e)})
    
    zip_buffer.seek(0)
    
    # 결과 요약
    success_count = sum(1 for r in results if r.get('success'))
    
    if success_count == 0:
        return jsonify({
            'success': False,
            'error': '모든 다운로드가 실패했습니다.',
            'results': results
        })
    
    # ZIP 파일 반환
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    filename = f"연차등록안내서_{timestamp}.zip"
    encoded_filename = quote(filename)
    
    return Response(
        zip_buffer.getvalue(),
        mimetype='application/zip',
        headers={
            'Content-Disposition': f"attachment; filename*=UTF-8''{encoded_filename}",
            'X-Download-Results': str(results)
        }
    )


def build_payload(ls_arr: list, additional: dict) -> dict:
    """arg1~arg47 payload 구성"""
    return {
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
        'arg44': additional.get('arg44', ''),
        'arg45': additional.get('arg45', ''),
        'arg46': additional.get('arg46', ''),
        'arg47': ls_arr[44] if len(ls_arr) > 44 else '',
    }


if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)

