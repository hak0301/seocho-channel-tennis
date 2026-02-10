"""
서초 채널 테니스 클럽 아이콘 생성 스크립트
"""

from PIL import Image, ImageDraw, ImageFont
import math
import os

def create_seocho_channel_icon(size=512):
    """서초 채널 테니스 클럽 공식 아이콘"""

    img = Image.new('RGBA', (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    center = size // 2
    padding = size // 32

    # 색상 정의
    dark_green = (27, 94, 32)        # #1B5E20
    medium_green = (76, 175, 80)     # #4CAF50
    tennis_yellow = (204, 255, 0)    # #CCFF00 - 테니스 공 색상
    gold = (255, 193, 7)             # #FFC107
    white = (255, 255, 255)

    # 배경 - 둥근 사각형 (앱 아이콘 스타일)
    corner_radius = size // 5
    draw.rounded_rectangle(
        [padding, padding, size - padding, size - padding],
        radius=corner_radius,
        fill=dark_green
    )

    # 테니스 공 (중앙, 크게)
    ball_radius = size // 3
    ball_x = center
    ball_y = center - size // 20

    # 테니스 공 그리기
    draw.ellipse(
        [ball_x - ball_radius, ball_y - ball_radius,
         ball_x + ball_radius, ball_y + ball_radius],
        fill=tennis_yellow
    )

    # 테니스 공 특유의 곡선 (흰색)
    curve_width = size // 25

    # 왼쪽 곡선
    draw.arc(
        [ball_x - ball_radius * 1.3, ball_y - ball_radius * 0.75,
         ball_x - ball_radius * 0.25, ball_y + ball_radius * 0.75],
        start=-65, end=65,
        fill=white, width=curve_width
    )

    # 오른쪽 곡선
    draw.arc(
        [ball_x + ball_radius * 0.25, ball_y - ball_radius * 0.75,
         ball_x + ball_radius * 1.3, ball_y + ball_radius * 0.75],
        start=115, end=245,
        fill=white, width=curve_width
    )

    # "SC" 텍스트 (공 안에)
    try:
        font_size = size // 4
        font = ImageFont.truetype("arialbd.ttf", font_size)
    except:
        try:
            font = ImageFont.truetype("arial.ttf", font_size)
        except:
            font = ImageFont.load_default()

    text = "SC"
    text_bbox = draw.textbbox((0, 0), text, font=font)
    text_width = text_bbox[2] - text_bbox[0]
    text_height = text_bbox[3] - text_bbox[1]
    text_x = ball_x - text_width // 2
    text_y = ball_y - text_height // 2 - size // 40

    # 텍스트 그림자
    draw.text((text_x + 3, text_y + 3), text, fill=(20, 60, 20), font=font)
    # 메인 텍스트
    draw.text((text_x, text_y), text, fill=dark_green, font=font)

    # 하단 골드 라인
    bar_height = size // 18
    bar_y = size - padding - size // 7
    bar_margin = size // 4

    draw.rounded_rectangle(
        [bar_margin, bar_y, size - bar_margin, bar_y + bar_height],
        radius=bar_height // 2,
        fill=gold
    )

    return img


if __name__ == "__main__":
    # 메인 아이콘 생성
    icon = create_seocho_channel_icon(512)

    output_dir = os.path.dirname(os.path.abspath(__file__))

    # 저장
    icon.save(os.path.join(output_dir, "icon.png"), "PNG")
    print("icon.png saved")

    # 다양한 크기로 저장
    for s in [192, 256, 512, 1024]:
        resized = icon.resize((s, s), Image.Resampling.LANCZOS)
        resized.save(os.path.join(output_dir, f"icon_{s}.png"), "PNG")
        print(f"icon_{s}.png saved")
