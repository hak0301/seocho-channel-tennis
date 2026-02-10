"""
서초 채널 테니스 클럽 아이콘 생성 스크립트
"""

from PIL import Image, ImageDraw, ImageFont, ImageFilter
import os

def create_seocho_channel_icon(size=512):
    """서초 채널 테니스 클럽 공식 아이콘 - 고해상도"""

    # 4배 크기로 그린 후 축소 (안티앨리어싱 효과)
    scale = 4
    large_size = size * scale

    img = Image.new('RGBA', (large_size, large_size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    center = large_size // 2
    padding = large_size // 32

    # 색상 정의
    dark_green = (27, 94, 32)        # #1B5E20
    tennis_yellow = (204, 255, 0)    # #CCFF00
    gold = (255, 193, 7)             # #FFC107
    white = (255, 255, 255)

    # 배경 - 둥근 사각형
    corner_radius = large_size // 5
    draw.rounded_rectangle(
        [padding, padding, large_size - padding, large_size - padding],
        radius=corner_radius,
        fill=dark_green
    )

    # 테니스 공 (중앙)
    ball_radius = large_size // 3
    ball_x = center
    ball_y = center - large_size // 20

    # 테니스 공 외곽선 (살짝 어두운 테두리)
    draw.ellipse(
        [ball_x - ball_radius - 4, ball_y - ball_radius - 4,
         ball_x + ball_radius + 4, ball_y + ball_radius + 4],
        fill=(180, 220, 0)
    )

    # 테니스 공
    draw.ellipse(
        [ball_x - ball_radius, ball_y - ball_radius,
         ball_x + ball_radius, ball_y + ball_radius],
        fill=tennis_yellow
    )

    # 테니스 공 곡선 (두껍게)
    curve_width = large_size // 20

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

    # "SC" 텍스트
    try:
        font_size = large_size // 4
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
    text_y = ball_y - text_height // 2 - large_size // 40

    # 텍스트 그림자 (더 부드럽게)
    for offset in [(4, 4), (3, 3), (2, 2)]:
        draw.text((text_x + offset[0], text_y + offset[1]), text, fill=(20, 70, 20, 150), font=font)

    # 메인 텍스트
    draw.text((text_x, text_y), text, fill=dark_green, font=font)

    # 하단 골드 바
    bar_height = large_size // 16
    bar_y = large_size - padding - large_size // 7
    bar_margin = large_size // 4

    draw.rounded_rectangle(
        [bar_margin, bar_y, large_size - bar_margin, bar_y + bar_height],
        radius=bar_height // 2,
        fill=gold
    )

    # 고품질 다운샘플링
    img = img.resize((size, size), Image.Resampling.LANCZOS)

    return img


if __name__ == "__main__":
    output_dir = os.path.dirname(os.path.abspath(__file__))

    # 1024 크기로 생성 (고해상도)
    icon = create_seocho_channel_icon(1024)
    icon.save(os.path.join(output_dir, "icon.png"), "PNG")
    print("icon.png saved (1024px)")

    # 다양한 크기
    for s in [192, 256, 512]:
        resized = icon.resize((s, s), Image.Resampling.LANCZOS)
        resized.save(os.path.join(output_dir, f"icon_{s}.png"), "PNG")
        print(f"icon_{s}.png saved")
