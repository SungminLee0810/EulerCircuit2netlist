#!/bin/bash

# 스크립트 사용법: ./process_json.sh <입력_폴더> <출력_폴더>

# 인자 개수 확인
if [ "$#" -ne 2 ]; then
    echo "사용법: $0 <입력_폴더> <출력_폴더>"
    exit 1
fi

INPUT_FOLDER=$1
OUTPUT_FOLDER=$2

# 출력 폴더가 존재하지 않으면 생성
mkdir -p "$OUTPUT_FOLDER"

# 입력 폴더 내의 모든 .json 파일에 대해 반복
for json_file in "$INPUT_FOLDER"/*.json; do
    # .json 파일이 없는 경우를 대비
    if [ ! -f "$json_file" ]; then
        echo "경고: '$INPUT_FOLDER'에 .json 파일이 없습니다."
        continue
    fi

    # 파일 이름 (확장자 제외) 추출
    base_name=$(basename "$json_file" .json)

    # 출력 파일 경로 설정
    svg_file="$OUTPUT_FOLDER/$base_name.svg"
    png_file="$OUTPUT_FOLDER/$base_name.png"

    echo "처리 중: $json_file"

    # netlistsvg 명령 실행하여 SVG 생성
    netlistsvg "$json_file" -o "$svg_file"

    # SVG 파일이 성공적으로 생성되었는지 확인
    if [ -f "$svg_file" ]; then
        echo "SVG 파일 생성됨: $svg_file"
        # convert 명령 실행하여 PNG 생성
        convert "$svg_file" "$png_file"
        if [ -f "$png_file" ]; then
            echo "PNG 파일 생성됨: $png_file"
        else
            echo "오류: PNG 파일을 생성하지 못했습니다: $png_file"
        fi
    else
        echo "오류: SVG 파일을 생성하지 못했습니다: $svg_file"
    fi
done

echo "모든 작업이 완료되었습니다." 