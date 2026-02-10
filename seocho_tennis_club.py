"""
서초 채널 테니스 클럽 관리 앱
- 운영 시간: 목요일 19:00-22:00, 일요일 17:00-20:00 (각 3시간)
- 복식 경기 전용
- 자동 매칭: 30분에 6게임 기준
"""

import flet as ft
import json
import os
import random
from datetime import datetime, timedelta
from typing import Optional, List
import uuid

from firebase_config import fb_get, fb_put, fb_patch, is_firebase_configured

# 데이터 파일 경로 (로컬 폴백용)
DATA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data")
MEMBERS_FILE = os.path.join(DATA_DIR, "members.json")
ATTENDANCE_FILE = os.path.join(DATA_DIR, "attendance.json")
MATCHES_FILE = os.path.join(DATA_DIR, "matches.json")

# 운영 설정
MIN_ATTENDANCE = 8
MAX_ATTENDANCE = 16
NUM_COURTS = 2
COURT_NAMES = ["7번코트", "8번코트"]
MATCH_DURATION_MIN = 30

# 요일별 타임 스케줄 (시작시간 리스트)
SCHEDULE = {
    "목": {
        "times": ["19:00", "19:30", "20:00", "20:30", "21:00"],
        "label": "목요일 19:00 - 22:00",
    },
    "일": {
        "times": ["17:00", "17:30", "18:00", "18:30", "19:00"],
        "label": "일요일 17:00 - 20:00",
    },
}

def get_today_schedule():
    """오늘 요일에 맞는 스케줄 반환, 없으면 목요일 기본값"""
    day_name = ["월", "화", "수", "목", "금", "토", "일"][datetime.now().weekday()]
    return SCHEDULE.get(day_name, SCHEDULE["목"])


# ==================== 디자인 테마 ====================
class AppTheme:
    """앱 디자인 테마"""
    # 메인 컬러
    PRIMARY = "#1B5E20"           # 진한 녹색
    PRIMARY_LIGHT = "#4CAF50"     # 밝은 녹색
    PRIMARY_DARK = "#0D3311"      # 아주 진한 녹색
    SECONDARY = "#FFC107"         # 골드/앰버
    ACCENT = "#C8E6C9"            # 연한 녹색

    # 배경색
    BG_PRIMARY = "#FAFAFA"        # 메인 배경
    BG_CARD = "#FFFFFF"           # 카드 배경
    BG_DARK = "#1B5E20"           # 어두운 배경

    # 텍스트 색상
    TEXT_PRIMARY = "#212121"      # 메인 텍스트
    TEXT_SECONDARY = "#757575"    # 보조 텍스트
    TEXT_ON_PRIMARY = "#FFFFFF"   # 프라이머리 위 텍스트

    # 상태 색상
    SUCCESS = "#43A047"
    WARNING = "#FB8C00"
    ERROR = "#E53935"

    # 그림자 및 효과
    SHADOW = ft.BoxShadow(
        spread_radius=1,
        blur_radius=8,
        color=ft.Colors.with_opacity(0.15, ft.Colors.BLACK),
        offset=ft.Offset(0, 2),
    )

    CARD_SHADOW = ft.BoxShadow(
        spread_radius=0,
        blur_radius=12,
        color=ft.Colors.with_opacity(0.1, ft.Colors.BLACK),
        offset=ft.Offset(0, 4),
    )


def ensure_data_dir():
    if not os.path.exists(DATA_DIR):
        os.makedirs(DATA_DIR)


# Firebase 경로 매핑
_FB_PATH_MAP = {
    MEMBERS_FILE: "members",
    ATTENDANCE_FILE: "attendance",
    MATCHES_FILE: "matches",
}


def load_json(file_path: str, default: dict) -> dict:
    """Firebase에서 로드, 실패 시 로컬 JSON 폴백"""
    fb_path = _FB_PATH_MAP.get(file_path)
    if fb_path:
        data = fb_get(fb_path, default=None)
        if data is not None:
            return data
    # 로컬 폴백
    if os.path.exists(file_path):
        with open(file_path, 'r', encoding='utf-8') as f:
            return json.load(f)
    return default


def save_json(file_path: str, data: dict):
    """Firebase에 저장 + 로컬 캐시도 저장"""
    ensure_data_dir()
    # 로컬 저장
    with open(file_path, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    # Firebase 저장
    fb_path = _FB_PATH_MAP.get(file_path)
    if fb_path:
        fb_put(fb_path, data)


def generate_id(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex[:8]}"


def get_week_range(date: datetime) -> tuple:
    start = date - timedelta(days=date.weekday())
    end = start + timedelta(days=6)
    return start, end


def get_month_range(date: datetime) -> tuple:
    start = date.replace(day=1)
    if date.month == 12:
        end = date.replace(year=date.year + 1, month=1, day=1) - timedelta(days=1)
    else:
        end = date.replace(month=date.month + 1, day=1) - timedelta(days=1)
    return start, end


def generate_random_matches(player_ids: List[str], schedule=None, num_courts: int = NUM_COURTS) -> List[dict]:
    """2코트 동시 진행 매칭 생성 (시간대별, 코트 공정 배분)"""
    if len(player_ids) < 4:
        return []

    if schedule is None:
        schedule = get_today_schedule()
    time_labels = schedule["times"]

    matches = []
    play_count = {pid: 0 for pid in player_ids}
    court_count = {pid: {court: 0 for court in COURT_NAMES} for pid in player_ids}
    match_num = 0

    for slot_idx, start_time in enumerate(time_labels):
        # 참여 횟수가 적은 순 → 같으면 랜덤
        sorted_players = sorted(player_ids, key=lambda x: (play_count[x], random.random()))

        # 이번 타임에 배정할 코트 수 결정 (인원 부족 시 1코트만)
        courts_this_slot = min(num_courts, len(sorted_players) // 4)
        if courts_this_slot == 0:
            continue

        needed = courts_this_slot * 4
        selected = sorted_players[:needed]

        # 코트 공정 배분: 각 선수의 코트 사용 횟수를 고려하여 배정
        if courts_this_slot == 2 and len(selected) == 8:
            # 8명을 두 코트에 배분할 때, 코트 편중을 줄이도록 배정
            random.shuffle(selected)
            # 각 선수의 7번코트 사용비율 계산 (낮은 사람이 7번코트로)
            court0_name = COURT_NAMES[0]
            court1_name = COURT_NAMES[1]
            selected.sort(key=lambda x: (court_count[x][court0_name] - court_count[x][court1_name], random.random()))
            group_a = selected[:4]  # 7번코트 적게 간 사람들
            group_b = selected[4:]  # 8번코트 적게 간 사람들
            random.shuffle(group_a)
            random.shuffle(group_b)
            groups = [group_a, group_b]
        else:
            random.shuffle(selected)
            groups = [selected[i*4:(i+1)*4] for i in range(courts_this_slot)]

        for court_idx, court_players in enumerate(groups):
            team1 = court_players[:2]
            team2 = court_players[2:]
            match_num += 1
            court_name = COURT_NAMES[court_idx] if court_idx < len(COURT_NAMES) else f"{court_idx+1}번코트"

            matches.append({
                "match_num": match_num,
                "time_slot": slot_idx + 1,
                "start_time": start_time,
                "court": court_name,
                "team1": team1,
                "team2": team2,
            })

            for pid in court_players:
                play_count[pid] += 1
                court_count[pid][court_name] += 1

    return matches


# ==================== 커스텀 컴포넌트 ====================

def create_styled_card(content, padding=16, margin=None):
    """세련된 카드 컴포넌트"""
    return ft.Container(
        content=content,
        padding=padding,
        margin=margin or ft.margin.only(bottom=12),
        bgcolor=AppTheme.BG_CARD,
        border_radius=16,
        shadow=AppTheme.CARD_SHADOW,
    )


def create_header_card(title: str, subtitle: str = None, icon: str = None, on_back=None):
    """헤더 카드 컴포넌트 (뒤로가기 버튼 포함)"""
    back_button = ft.IconButton(
        icon=ft.Icons.ARROW_BACK,
        icon_color=AppTheme.TEXT_ON_PRIMARY,
        icon_size=24,
        on_click=on_back,
    ) if on_back else ft.Container(width=0)

    content = ft.Column([
        ft.Row([
            back_button,
            ft.Icon(icon, color=AppTheme.TEXT_ON_PRIMARY, size=28) if icon else ft.Container(),
            ft.Text(title, size=22, weight=ft.FontWeight.BOLD, color=AppTheme.TEXT_ON_PRIMARY),
        ], spacing=8),
        ft.Text(subtitle, size=14, color=ft.Colors.with_opacity(0.9, AppTheme.TEXT_ON_PRIMARY)) if subtitle else ft.Container(),
    ], spacing=4)

    return ft.Container(
        content=content,
        padding=ft.padding.symmetric(horizontal=12, vertical=20),
        bgcolor=AppTheme.PRIMARY,
        border_radius=ft.border_radius.only(bottom_left=24, bottom_right=24),
        shadow=AppTheme.SHADOW,
    )


def create_stat_box(value: str, label: str, color: str = None):
    """통계 박스 컴포넌트"""
    return ft.Container(
        content=ft.Column([
            ft.Text(value, size=28, weight=ft.FontWeight.BOLD, color=color or AppTheme.PRIMARY),
            ft.Text(label, size=12, color=AppTheme.TEXT_SECONDARY),
        ], horizontal_alignment=ft.CrossAxisAlignment.CENTER, spacing=4),
        padding=16,
        expand=True,
        bgcolor=AppTheme.BG_CARD,
        border_radius=12,
        shadow=AppTheme.SHADOW,
    )


def create_primary_button(text: str, icon: str = None, on_click=None, width=None):
    """프라이머리 버튼"""
    return ft.ElevatedButton(
        content=ft.Row([
            ft.Icon(icon, size=20, color=AppTheme.TEXT_ON_PRIMARY) if icon else ft.Container(),
            ft.Text(text, size=14, weight=ft.FontWeight.W_600),
        ], alignment=ft.MainAxisAlignment.CENTER, spacing=8, tight=True),
        on_click=on_click,
        bgcolor=AppTheme.PRIMARY,
        color=AppTheme.TEXT_ON_PRIMARY,
        elevation=2,
        style=ft.ButtonStyle(
            shape=ft.RoundedRectangleBorder(radius=12),
            padding=ft.padding.symmetric(horizontal=20, vertical=12),
        ),
        width=width,
    )


def create_secondary_button(text: str, icon: str = None, on_click=None, color=None):
    """세컨더리 버튼"""
    btn_color = color or AppTheme.PRIMARY
    return ft.OutlinedButton(
        content=ft.Row([
            ft.Icon(icon, size=18, color=btn_color) if icon else ft.Container(),
            ft.Text(text, size=14, color=btn_color),
        ], alignment=ft.MainAxisAlignment.CENTER, spacing=8, tight=True),
        on_click=on_click,
        style=ft.ButtonStyle(
            shape=ft.RoundedRectangleBorder(radius=12),
            padding=ft.padding.symmetric(horizontal=16, vertical=10),
            side=ft.BorderSide(1.5, btn_color),
        ),
    )


def create_member_card(name: str, subtitle: str = None, on_edit=None, on_delete=None):
    """회원 카드 컴포넌트"""
    return ft.Container(
        content=ft.Row([
            ft.Container(
                content=ft.Text(name[0] if name else "?", size=18, weight=ft.FontWeight.BOLD, color=AppTheme.TEXT_ON_PRIMARY),
                width=44,
                height=44,
                bgcolor=AppTheme.PRIMARY_LIGHT,
                border_radius=22,
                alignment=ft.Alignment(0, 0),
            ),
            ft.Column([
                ft.Text(name, size=16, weight=ft.FontWeight.W_600, color=AppTheme.TEXT_PRIMARY),
                ft.Text(subtitle or "", size=12, color=AppTheme.TEXT_SECONDARY) if subtitle else ft.Container(),
            ], spacing=2, expand=True),
            ft.IconButton(
                icon=ft.Icons.EDIT_OUTLINED,
                icon_color=AppTheme.TEXT_SECONDARY,
                icon_size=20,
                on_click=on_edit,
            ) if on_edit else ft.Container(),
            ft.IconButton(
                icon=ft.Icons.DELETE_OUTLINE,
                icon_color=AppTheme.ERROR,
                icon_size=20,
                on_click=on_delete,
            ) if on_delete else ft.Container(),
        ], spacing=12),
        padding=12,
        bgcolor=AppTheme.BG_CARD,
        border_radius=12,
        margin=ft.margin.only(bottom=8),
        shadow=ft.BoxShadow(
            spread_radius=0,
            blur_radius=4,
            color=ft.Colors.with_opacity(0.08, ft.Colors.BLACK),
            offset=ft.Offset(0, 2),
        ),
    )


def create_match_result_card(match_num: int, team1_names: str, team2_names: str,
                              score1: int, score2: int, on_delete=None,
                              court: str = "", time_slot: int = 0, start_time: str = ""):
    """경기 결과 카드 컴포넌트"""
    is_draw = score1 == score2
    is_team1_winner = score1 > score2
    is_team2_winner = score2 > score1

    # 무승부일 때 색상
    draw_color = AppTheme.WARNING

    # 팀1 색상 결정
    if is_draw:
        team1_color = draw_color
        team1_weight = ft.FontWeight.BOLD
    elif is_team1_winner:
        team1_color = AppTheme.SUCCESS
        team1_weight = ft.FontWeight.BOLD
    else:
        team1_color = AppTheme.TEXT_PRIMARY
        team1_weight = ft.FontWeight.NORMAL

    # 팀2 색상 결정
    if is_draw:
        team2_color = draw_color
        team2_weight = ft.FontWeight.BOLD
    elif is_team2_winner:
        team2_color = AppTheme.SUCCESS
        team2_weight = ft.FontWeight.BOLD
    else:
        team2_color = AppTheme.TEXT_PRIMARY
        team2_weight = ft.FontWeight.NORMAL

    # 무승부 표시
    result_badge = None
    if is_draw:
        result_badge = ft.Container(
            content=ft.Text("DRAW", size=10, color=AppTheme.TEXT_ON_PRIMARY, weight=ft.FontWeight.BOLD),
            bgcolor=draw_color,
            padding=ft.padding.symmetric(horizontal=8, vertical=2),
            border_radius=8,
        )

    # 코트 배지
    court_badge = None
    if court:
        court_badge = ft.Container(
            content=ft.Text(court, size=10, color=AppTheme.TEXT_ON_PRIMARY, weight=ft.FontWeight.BOLD),
            bgcolor=AppTheme.SECONDARY,
            padding=ft.padding.symmetric(horizontal=8, vertical=2),
            border_radius=8,
        )

    # 시작시간 배지
    time_badge = None
    if start_time:
        time_badge = ft.Container(
            content=ft.Text(start_time, size=10, color=AppTheme.PRIMARY, weight=ft.FontWeight.BOLD),
            bgcolor=AppTheme.ACCENT,
            padding=ft.padding.symmetric(horizontal=8, vertical=2),
            border_radius=8,
        )

    return ft.Container(
        content=ft.Column([
            ft.Row([
                ft.Container(
                    content=ft.Text(f"#{match_num}", size=12, color=AppTheme.TEXT_ON_PRIMARY, weight=ft.FontWeight.BOLD),
                    bgcolor=AppTheme.PRIMARY_LIGHT,
                    padding=ft.padding.symmetric(horizontal=10, vertical=4),
                    border_radius=12,
                ),
                court_badge if court_badge else ft.Container(),
                time_badge if time_badge else ft.Container(),
                result_badge if result_badge else ft.Container(),
                ft.Container(expand=True),
                ft.IconButton(
                    icon=ft.Icons.DELETE_OUTLINE,
                    icon_color=AppTheme.ERROR,
                    icon_size=18,
                    on_click=on_delete,
                ) if on_delete else ft.Container(),
            ]),
            ft.Row([
                ft.Column([
                    ft.Text(
                        team1_names,
                        size=14,
                        weight=team1_weight,
                        color=team1_color,
                        text_align=ft.TextAlign.CENTER,
                    ),
                    ft.Container(
                        content=ft.Text(str(score1), size=32, weight=ft.FontWeight.BOLD,
                                        color=team1_color if is_draw or is_team1_winner else AppTheme.TEXT_SECONDARY),
                        padding=ft.padding.symmetric(vertical=8),
                    ),
                ], horizontal_alignment=ft.CrossAxisAlignment.CENTER, expand=True),
                ft.Container(
                    content=ft.Text("VS", size=14, color=AppTheme.TEXT_SECONDARY, weight=ft.FontWeight.BOLD),
                    padding=ft.padding.symmetric(horizontal=16),
                ),
                ft.Column([
                    ft.Text(
                        team2_names,
                        size=14,
                        weight=team2_weight,
                        color=team2_color,
                        text_align=ft.TextAlign.CENTER,
                    ),
                    ft.Container(
                        content=ft.Text(str(score2), size=32, weight=ft.FontWeight.BOLD,
                                        color=team2_color if is_draw or is_team2_winner else AppTheme.TEXT_SECONDARY),
                        padding=ft.padding.symmetric(vertical=8),
                    ),
                ], horizontal_alignment=ft.CrossAxisAlignment.CENTER, expand=True),
            ], alignment=ft.MainAxisAlignment.SPACE_AROUND),
        ], spacing=8),
        padding=16,
        bgcolor=AppTheme.BG_CARD,
        border_radius=16,
        margin=ft.margin.only(bottom=12),
        shadow=AppTheme.CARD_SHADOW,
    )


def create_ranking_card(rank: int, name: str, points: int, wins: int, losses: int,
                         games_won: int, games_lost: int, draws: int = 0):
    """순위 카드 컴포넌트"""
    # 순위별 배경색
    if rank == 1:
        rank_bg = "#FFD700"  # 금
        rank_color = "#7B5800"
    elif rank == 2:
        rank_bg = "#C0C0C0"  # 은
        rank_color = "#5A5A5A"
    elif rank == 3:
        rank_bg = "#CD7F32"  # 동
        rank_color = "#5D3A1A"
    else:
        rank_bg = AppTheme.ACCENT
        rank_color = AppTheme.PRIMARY

    # 전적 표시 (무승부 포함)
    record_text = f"{wins}승 {losses}패"
    if draws > 0:
        record_text = f"{wins}승 {draws}무 {losses}패"

    return ft.Container(
        content=ft.Row([
            ft.Container(
                content=ft.Text(str(rank), size=18, weight=ft.FontWeight.BOLD, color=rank_color),
                width=44,
                height=44,
                bgcolor=rank_bg,
                border_radius=12,
                alignment=ft.Alignment(0, 0),
            ),
            ft.Column([
                ft.Text(name, size=16, weight=ft.FontWeight.W_600, color=AppTheme.TEXT_PRIMARY),
                ft.Text(
                    f"{record_text} · 게임 {games_won}-{games_lost}",
                    size=12,
                    color=AppTheme.TEXT_SECONDARY
                ),
            ], spacing=2, expand=True),
            ft.Column([
                ft.Text(
                    f"{points:+d}",
                    size=24,
                    weight=ft.FontWeight.BOLD,
                    color=AppTheme.SUCCESS if points >= 0 else AppTheme.ERROR,
                ),
                ft.Text("점", size=12, color=AppTheme.TEXT_SECONDARY),
            ], horizontal_alignment=ft.CrossAxisAlignment.CENTER),
        ], spacing=16),
        padding=16,
        bgcolor=AppTheme.BG_CARD,
        border_radius=16,
        margin=ft.margin.only(bottom=10),
        shadow=AppTheme.CARD_SHADOW,
    )


# ==================== 메인 앱 클래스 ====================

class TennisClubApp:
    def __init__(self, page: ft.Page):
        self.page = page
        self.page.title = "seocho-channel"

        # 윈도우 아이콘 설정 (Windows에서는 .ico 파일 필요)
        icon_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "assets", "icon.ico")
        if os.path.exists(icon_path):
            self.page.window.icon = icon_path

        self.page.theme_mode = ft.ThemeMode.LIGHT
        self.page.bgcolor = AppTheme.BG_PRIMARY
        self.page.padding = 0
        self.page.spacing = 0

        # 폰트 설정
        self.page.fonts = {
            "Pretendard": "https://cdn.jsdelivr.net/gh/orioncactus/pretendard/dist/web/static/pretendard.css"
        }

        # 데이터 로드
        self.members = load_json(MEMBERS_FILE, {"members": []})
        self.attendance = load_json(ATTENDANCE_FILE, {"attendance": []})
        self.matches = load_json(MATCHES_FILE, {"matches": []})

        self.selected_date = datetime.now().strftime("%Y-%m-%d")
        self.auto_match_schedule = []
        self.current_user = None  # 로그인한 사용자 이름

        # 현재 화면 상태 추적 (홈=0, 서브메뉴=1)
        self.current_view = 0

        # 뒤로가기 핸들러 (Android)
        self.page.on_view_pop = self.on_view_pop

        # ESC 키 핸들러 (데스크탑)
        self.page.on_keyboard_event = self.on_keyboard_event

        self.show_login_screen()

    def on_view_pop(self, e):
        """Android 뒤로가기 버튼 처리"""
        if self.current_view > 0:
            self.show_home_tab()
            self.page.update()
            return False  # 앱 종료 방지
        return True  # 홈에서는 기본 동작 (앱 종료)

    def go_back_to_home(self, e=None):
        """홈으로 돌아가기"""
        self.current_view = 0
        self.show_home_tab()

    def on_keyboard_event(self, e: ft.KeyboardEvent):
        """ESC 키로 뒤로가기 (데스크탑)"""
        if e.key == "Escape" and self.current_view > 0:
            self.go_back_to_home()

    def show_login_screen(self):
        """로그인 화면 - 이름 선택 또는 입력"""
        member_names = [m["name"] for m in self.members.get("members", [])]

        typed_name = {"value": ""}

        def on_name_change(e):
            typed_name["value"] = e.control.value or ""

        name_field = ft.TextField(
            label="이름 직접 입력",
            border_radius=12,
            border_color=AppTheme.PRIMARY_LIGHT,
            focused_border_color=AppTheme.PRIMARY,
            prefix_icon=ft.Icons.PERSON,
            on_change=on_name_change,
            on_submit=lambda e: login_with_name(typed_name["value"]),
        )

        # Firebase 연결 상태 표시
        if is_firebase_configured():
            connection_badge = ft.Container(
                content=ft.Row([
                    ft.Icon(ft.Icons.CLOUD_DONE, size=16, color=AppTheme.SUCCESS),
                    ft.Text("Firebase 연결됨", size=12, color=AppTheme.SUCCESS),
                ], spacing=4),
                padding=ft.padding.symmetric(horizontal=12, vertical=4),
                border_radius=12,
                bgcolor=ft.Colors.with_opacity(0.1, AppTheme.SUCCESS),
            )
        else:
            connection_badge = ft.Container(
                content=ft.Row([
                    ft.Icon(ft.Icons.CLOUD_OFF, size=16, color=AppTheme.WARNING),
                    ft.Text("오프라인 모드", size=12, color=AppTheme.WARNING),
                ], spacing=4),
                padding=ft.padding.symmetric(horizontal=12, vertical=4),
                border_radius=12,
                bgcolor=ft.Colors.with_opacity(0.1, AppTheme.WARNING),
            )

        def login_with_name(name):
            if name and name.strip():
                try:
                    self.current_user = name.strip()
                    self.page.clean()
                    self.setup_ui()
                except Exception as ex:
                    self.page.clean()
                    self.page.add(ft.Text(f"오류: {ex}", color="red", size=16))
                    self.page.update()

        def on_member_click(e, name):
            login_with_name(name)

        def on_login_click(e):
            login_with_name(typed_name["value"] or name_field.value)

        # 기존 회원 버튼 리스트
        member_buttons = []
        for name in member_names:
            member_buttons.append(
                ft.Container(
                    content=ft.Row([
                        ft.Container(
                            content=ft.Text(name[0], size=16, weight=ft.FontWeight.BOLD, color=AppTheme.TEXT_ON_PRIMARY),
                            width=40, height=40,
                            bgcolor=AppTheme.PRIMARY_LIGHT,
                            border_radius=20,
                            alignment=ft.Alignment(0, 0),
                        ),
                        ft.Text(name, size=15, weight=ft.FontWeight.W_500, color=AppTheme.TEXT_PRIMARY),
                    ], spacing=12),
                    padding=12,
                    bgcolor=AppTheme.BG_CARD,
                    border_radius=12,
                    on_click=lambda e, n=name: on_member_click(e, n),
                    shadow=ft.BoxShadow(spread_radius=0, blur_radius=4,
                                        color=ft.Colors.with_opacity(0.08, ft.Colors.BLACK),
                                        offset=ft.Offset(0, 2)),
                )
            )

        member_list = ft.ListView(
            controls=member_buttons,
            spacing=8,
            height=300,
            padding=ft.padding.symmetric(horizontal=4),
        ) if member_buttons else ft.Container(
            content=ft.Text("등록된 회원이 없습니다", size=14, color=AppTheme.TEXT_SECONDARY),
            padding=20,
            alignment=ft.Alignment(0, 0),
        )

        content = ft.Column([
            ft.Container(
                content=ft.Column([
                    ft.Container(
                        content=ft.Icon(ft.Icons.SPORTS_TENNIS, size=40, color=AppTheme.PRIMARY),
                        width=72, height=72,
                        bgcolor="#CCFF00",
                        border_radius=20,
                        alignment=ft.Alignment(0, 0),
                    ),
                    ft.Text("서초 채널", size=28, weight=ft.FontWeight.BOLD, color=AppTheme.TEXT_ON_PRIMARY),
                    ft.Text("TENNIS CLUB", size=14, color=ft.Colors.with_opacity(0.8, AppTheme.TEXT_ON_PRIMARY)),
                    ft.Container(height=8),
                    connection_badge,
                ], horizontal_alignment=ft.CrossAxisAlignment.CENTER, spacing=4),
                padding=ft.padding.only(top=60, bottom=30),
                bgcolor=AppTheme.PRIMARY,
                border_radius=ft.border_radius.only(bottom_left=32, bottom_right=32),
                alignment=ft.Alignment(0, 0),
            ),

            ft.Container(
                content=ft.Column([
                    ft.Text("회원 선택", size=16, weight=ft.FontWeight.BOLD, color=AppTheme.TEXT_PRIMARY),
                    member_list,
                    ft.Divider(),
                    ft.Text("또는 이름 입력", size=14, color=AppTheme.TEXT_SECONDARY),
                    name_field,
                    ft.Container(height=8),
                    create_primary_button("입장", ft.Icons.LOGIN, on_login_click, width=200),
                ], horizontal_alignment=ft.CrossAxisAlignment.CENTER, spacing=8),
                padding=ft.padding.symmetric(horizontal=24, vertical=16),
            ),
        ], spacing=0, scroll=ft.ScrollMode.AUTO, expand=True, horizontal_alignment=ft.CrossAxisAlignment.CENTER)

        self.page.add(content)
        self.page.update()

    def reload_data(self):
        """Firebase에서 최신 데이터 다시 로드"""
        self.members = load_json(MEMBERS_FILE, {"members": []})
        self.attendance = load_json(ATTENDANCE_FILE, {"attendance": []})
        self.matches = load_json(MATCHES_FILE, {"matches": []})

    def setup_ui(self):
        self.tab_content = ft.Container(expand=True, bgcolor=AppTheme.BG_PRIMARY)
        self.selected_tab = 0

        self.page.add(
            ft.Column(
                controls=[self.tab_content],
                expand=True,
                spacing=0
            )
        )

        self.show_home_tab()

    def create_tab_buttons(self):
        tabs = [
            ("홈", ft.Icons.HOME),
            ("회원", ft.Icons.PEOPLE),
            ("출석", ft.Icons.HOW_TO_REG),
            ("경기", ft.Icons.SPORTS_TENNIS),
            ("순위", ft.Icons.EMOJI_EVENTS),
            ("설정", ft.Icons.SETTINGS),
        ]
        buttons = []
        for i, (label, icon) in enumerate(tabs):
            is_selected = i == self.selected_tab
            buttons.append(
                ft.Container(
                    content=ft.Row([
                        ft.Icon(icon, size=18, color=AppTheme.PRIMARY if is_selected else AppTheme.TEXT_ON_PRIMARY),
                        ft.Text(label, size=13, weight=ft.FontWeight.BOLD if is_selected else ft.FontWeight.NORMAL,
                               color=AppTheme.PRIMARY if is_selected else AppTheme.TEXT_ON_PRIMARY),
                    ], spacing=4, alignment=ft.MainAxisAlignment.CENTER),
                    bgcolor=AppTheme.BG_CARD if is_selected else ft.Colors.TRANSPARENT,
                    border_radius=20,
                    padding=ft.padding.symmetric(horizontal=12, vertical=8),
                    on_click=lambda e, idx=i: self.on_tab_click(idx),
                )
            )
        return buttons

    def on_tab_click(self, index):
        # 홈이 삭제되었으므로 인덱스 매핑: 0=회원, 1=출석, 2=경기, 3=순위, 4=설정
        self.selected_tab = index
        self.current_view = 1  # 서브메뉴로 이동
        tabs = [
            self.show_members_tab,      # 0
            self.show_attendance_tab,   # 1
            self.show_match_tab,        # 2
            self.show_ranking_tab,      # 3
            self.show_settings_tab,     # 4
        ]
        if 0 <= index < len(tabs):
            tabs[index]()

    def on_nav_change(self, e):
        index = e.control.selected_index
        tabs = [
            self.show_home_tab,
            self.show_members_tab,
            self.show_attendance_tab,
            self.show_match_tab,
            self.show_ranking_tab,
            self.show_settings_tab,
        ]
        tabs[index]()

    # ==================== 홈 탭 ====================
    def show_home_tab(self):
        self.current_view = 0  # 홈 화면
        self.reload_data()  # 최신 데이터 동기화
        today = datetime.now()
        day_name = ["월", "화", "수", "목", "금", "토", "일"][today.weekday()]

        # 오늘 일정
        if today.weekday() == 3:
            schedule_text = "오늘 운영 19:00 - 22:00"
            schedule_icon = ft.Icons.PLAY_CIRCLE
            schedule_color = AppTheme.SUCCESS
        elif today.weekday() == 6:
            schedule_text = "오늘 운영 17:00 - 20:00"
            schedule_icon = ft.Icons.PLAY_CIRCLE
            schedule_color = AppTheme.SUCCESS
        else:
            days_until_thursday = (3 - today.weekday()) % 7 or 7
            days_until_sunday = (6 - today.weekday()) % 7 or 7

            if days_until_thursday < days_until_sunday:
                next_date = today + timedelta(days=days_until_thursday)
                schedule_text = f"다음 운영: {next_date.strftime('%m/%d')} (목) 19:00"
            else:
                next_date = today + timedelta(days=days_until_sunday)
                schedule_text = f"다음 운영: {next_date.strftime('%m/%d')} (일) 17:00"
            schedule_icon = ft.Icons.SCHEDULE
            schedule_color = AppTheme.SECONDARY

        total_members = len(self.members.get("members", []))
        total_matches = len(self.matches.get("matches", []))

        # 메뉴 버튼 생성 (홈 제외: 회원=0, 출석=1, 경기=2, 순위=3, 설정=4)
        def create_menu_button(icon, label, index):
            return ft.Container(
                content=ft.Column([
                    ft.Icon(icon, size=22, color=AppTheme.PRIMARY),
                    ft.Text(label, size=11, color=AppTheme.PRIMARY, weight=ft.FontWeight.W_500),
                ], spacing=2, horizontal_alignment=ft.CrossAxisAlignment.CENTER),
                padding=ft.padding.symmetric(vertical=6, horizontal=8),
                border_radius=12,
                bgcolor=AppTheme.ACCENT,
                on_click=lambda e, idx=index: self.on_tab_click(idx),
            )

        menu_bar = ft.Container(
            content=ft.Row([
                create_menu_button(ft.Icons.PEOPLE, "회원", 0),
                create_menu_button(ft.Icons.HOW_TO_REG, "출석", 1),
                create_menu_button(ft.Icons.SPORTS_TENNIS, "경기", 2),
                create_menu_button(ft.Icons.EMOJI_EVENTS, "순위", 3),
                create_menu_button(ft.Icons.SETTINGS, "설정", 4),
            ], alignment=ft.MainAxisAlignment.SPACE_AROUND),
            bgcolor=AppTheme.BG_CARD,
            border_radius=16,
            padding=ft.padding.symmetric(vertical=10, horizontal=8),
            shadow=AppTheme.CARD_SHADOW,
        )

        content = ft.Column([
            # 헤더
            ft.Container(
                content=ft.Column([
                    ft.Row([
                        ft.Container(
                            content=ft.Icon(ft.Icons.SPORTS_TENNIS, size=32, color=AppTheme.PRIMARY),
                            width=56,
                            height=56,
                            bgcolor="#CCFF00",
                            border_radius=16,
                            alignment=ft.Alignment(0, 0),
                        ),
                        ft.Column([
                            ft.Text("서초 채널", size=26, weight=ft.FontWeight.BOLD, color=AppTheme.TEXT_ON_PRIMARY),
                            ft.Text("TENNIS CLUB", size=14, color=ft.Colors.with_opacity(0.8, AppTheme.TEXT_ON_PRIMARY)),
                        ], spacing=0, expand=True),
                        ft.Container(
                            content=ft.Column([
                                ft.Icon(ft.Icons.PERSON, size=16, color=AppTheme.TEXT_ON_PRIMARY),
                                ft.Text(self.current_user or "게스트", size=11, color=AppTheme.TEXT_ON_PRIMARY),
                            ], horizontal_alignment=ft.CrossAxisAlignment.CENTER, spacing=2),
                            bgcolor=ft.Colors.with_opacity(0.2, ft.Colors.WHITE),
                            padding=ft.padding.symmetric(horizontal=10, vertical=6),
                            border_radius=12,
                        ),
                    ], spacing=16),
                    ft.Container(height=12),
                    # 임원 정보 (세로 배치)
                    ft.Container(
                        content=ft.Column([
                            ft.Row([
                                ft.Text("회장: 박현수", size=13, color=AppTheme.TEXT_ON_PRIMARY, weight=ft.FontWeight.W_500),
                                ft.Text("  |  ", size=13, color=ft.Colors.with_opacity(0.5, AppTheme.TEXT_ON_PRIMARY)),
                                ft.Text("부회장: 조대훈", size=13, color=AppTheme.TEXT_ON_PRIMARY, weight=ft.FontWeight.W_500),
                            ], alignment=ft.MainAxisAlignment.CENTER),
                            ft.Text("총무: 주웅렬", size=13, color=AppTheme.TEXT_ON_PRIMARY, weight=ft.FontWeight.W_500),
                        ], spacing=4, horizontal_alignment=ft.CrossAxisAlignment.CENTER),
                        bgcolor=ft.Colors.with_opacity(0.2, ft.Colors.WHITE),
                        padding=ft.padding.symmetric(horizontal=16, vertical=10),
                        border_radius=12,
                    ),
                    ft.Container(height=8),
                    ft.Container(
                        content=ft.Row([
                            ft.Icon(schedule_icon, color=schedule_color, size=20),
                            ft.Text(schedule_text, size=15, color=AppTheme.TEXT_ON_PRIMARY, weight=ft.FontWeight.W_500),
                        ], spacing=8),
                        bgcolor=ft.Colors.with_opacity(0.15, ft.Colors.WHITE),
                        padding=ft.padding.symmetric(horizontal=16, vertical=10),
                        border_radius=12,
                    ),
                ]),
                padding=ft.padding.only(left=24, right=24, top=20, bottom=24),
                bgcolor=AppTheme.PRIMARY,
                border_radius=ft.border_radius.only(bottom_left=32, bottom_right=32),
            ),

            # 통계 (작게)
            ft.Container(
                content=ft.Row([
                    ft.Text("클럽 현황", size=14, weight=ft.FontWeight.BOLD, color=AppTheme.TEXT_PRIMARY),
                    ft.Container(width=16),
                    ft.Container(
                        content=ft.Row([
                            ft.Text(str(total_members), size=16, weight=ft.FontWeight.BOLD, color=AppTheme.PRIMARY),
                            ft.Text(" 회원", size=12, color=AppTheme.TEXT_SECONDARY),
                        ], spacing=2),
                    ),
                    ft.Container(width=16),
                    ft.Container(
                        content=ft.Row([
                            ft.Text(str(total_matches), size=16, weight=ft.FontWeight.BOLD, color=AppTheme.SECONDARY),
                            ft.Text(" 경기", size=12, color=AppTheme.TEXT_SECONDARY),
                        ], spacing=2),
                    ),
                ], alignment=ft.MainAxisAlignment.CENTER),
                padding=ft.padding.symmetric(horizontal=20, vertical=12),
            ),

            # 메뉴 바
            ft.Container(
                content=menu_bar,
                padding=ft.padding.symmetric(horizontal=20),
            ),

            # 클럽 사진
            ft.Container(
                content=ft.Column([
                    ft.Text("GALLERY", size=14, weight=ft.FontWeight.BOLD,
                            color=AppTheme.TEXT_SECONDARY, text_align=ft.TextAlign.CENTER),
                    ft.Container(
                        content=ft.Image(
                            src="photo1.jpg",
                            fit=ft.ImageFit.COVER,
                            border_radius=ft.border_radius.all(16),
                        ),
                        border_radius=16,
                        clip_behavior=ft.ClipBehavior.ANTI_ALIAS,
                        shadow=AppTheme.CARD_SHADOW,
                    ),
                    ft.Container(
                        content=ft.Image(
                            src="photo2.jpg",
                            fit=ft.ImageFit.COVER,
                            border_radius=ft.border_radius.all(16),
                        ),
                        border_radius=16,
                        clip_behavior=ft.ClipBehavior.ANTI_ALIAS,
                        shadow=AppTheme.CARD_SHADOW,
                    ),
                ], spacing=12, horizontal_alignment=ft.CrossAxisAlignment.CENTER),
                padding=ft.padding.symmetric(horizontal=20, vertical=16),
            ),
        ], spacing=0, scroll=ft.ScrollMode.AUTO, expand=True)

        self.tab_content.content = content
        self.page.update()

    # ==================== 회원 탭 ====================
    def show_members_tab(self):
        self.members_list = ft.ListView(expand=True, spacing=0, padding=ft.padding.symmetric(horizontal=20))
        self.update_members_list()

        content = ft.Column([
            create_header_card("회원 관리", f"총 {len(self.members.get('members', []))}명", ft.Icons.PEOPLE, lambda e: self.go_back_to_home()),
            ft.Container(
                content=create_primary_button("회원 등록", ft.Icons.PERSON_ADD, self.show_add_member_dialog),
                padding=ft.padding.symmetric(horizontal=20, vertical=16),
            ),
            self.members_list,
        ], spacing=0, expand=True)

        self.tab_content.content = content
        self.page.update()

    def update_members_list(self):
        self.members_list.controls.clear()
        for member in self.members.get("members", []):
            self.members_list.controls.append(
                create_member_card(
                    member["name"],
                    member.get("phone", ""),
                    on_edit=lambda e, m=member: self.show_edit_member_dialog(m),
                    on_delete=lambda e, m=member: self.delete_member(m),
                )
            )

    def show_add_member_dialog(self, e):
        name_field = ft.TextField(
            label="이름",
            autofocus=True,
            border_radius=12,
            border_color=AppTheme.PRIMARY_LIGHT,
            focused_border_color=AppTheme.PRIMARY,
        )
        phone_field = ft.TextField(
            label="연락처 (선택)",
            border_radius=12,
            border_color=AppTheme.PRIMARY_LIGHT,
            focused_border_color=AppTheme.PRIMARY,
        )

        def save_member(e):
            if name_field.value:
                new_member = {
                    "id": generate_id("m"),
                    "name": name_field.value,
                    "phone": phone_field.value or "",
                    "join_date": datetime.now().strftime("%Y-%m-%d")
                }
                self.members["members"].append(new_member)
                save_json(MEMBERS_FILE, self.members)
                self.page.close(dialog)
                self.show_members_tab()

        dialog = ft.AlertDialog(
            title=ft.Text("회원 등록", weight=ft.FontWeight.BOLD),
            content=ft.Column([name_field, phone_field], tight=True, spacing=16),
            actions=[
                ft.TextButton("취소", on_click=lambda e: self.page.close(dialog)),
                create_primary_button("등록", on_click=save_member),
            ],
            shape=ft.RoundedRectangleBorder(radius=20),
        )
        self.page.open(dialog)

    def show_edit_member_dialog(self, member: dict):
        name_field = ft.TextField(label="이름", value=member["name"], border_radius=12)
        phone_field = ft.TextField(label="연락처", value=member.get("phone", ""), border_radius=12)

        def update_member(e):
            if name_field.value:
                member["name"] = name_field.value
                member["phone"] = phone_field.value or ""
                save_json(MEMBERS_FILE, self.members)
                self.page.close(dialog)
                self.show_members_tab()

        dialog = ft.AlertDialog(
            title=ft.Text("회원 수정", weight=ft.FontWeight.BOLD),
            content=ft.Column([name_field, phone_field], tight=True, spacing=16),
            actions=[
                ft.TextButton("취소", on_click=lambda e: self.page.close(dialog)),
                create_primary_button("저장", on_click=update_member),
            ],
            shape=ft.RoundedRectangleBorder(radius=20),
        )
        self.page.open(dialog)

    def delete_member(self, member: dict):
        def confirm_delete(e):
            self.members["members"] = [m for m in self.members["members"] if m["id"] != member["id"]]
            save_json(MEMBERS_FILE, self.members)
            self.page.close(dialog)
            self.show_members_tab()

        dialog = ft.AlertDialog(
            title=ft.Text("회원 삭제", weight=ft.FontWeight.BOLD),
            content=ft.Text(f"'{member['name']}' 회원을 삭제하시겠습니까?"),
            actions=[
                ft.TextButton("취소", on_click=lambda e: self.page.close(dialog)),
                ft.ElevatedButton("삭제", on_click=confirm_delete, bgcolor=AppTheme.ERROR, color=AppTheme.TEXT_ON_PRIMARY),
            ],
            shape=ft.RoundedRectangleBorder(radius=20),
        )
        self.page.open(dialog)

    # ==================== 출석 탭 ====================
    def show_attendance_tab(self):
        self.attendance_date = datetime.now().strftime("%Y-%m-%d")
        self.attendance_checks = {}

        date_picker = ft.DatePicker(
            on_change=self.on_attendance_date_change,
            first_date=datetime(2024, 1, 1),
            last_date=datetime(2030, 12, 31),
        )
        self.page.overlay.append(date_picker)

        self.attendance_date_text = ft.Text(self.attendance_date, size=16, weight=ft.FontWeight.BOLD, color=AppTheme.TEXT_ON_PRIMARY)
        self.attendance_count_text = ft.Text("0명", size=24, weight=ft.FontWeight.BOLD, color=AppTheme.TEXT_ON_PRIMARY)
        self.attendance_list = ft.ListView(expand=True, spacing=8, padding=ft.padding.symmetric(horizontal=20))

        self.load_attendance_for_date()

        content = ft.Column([
            # 헤더
            ft.Container(
                content=ft.Column([
                    ft.Row([
                        ft.IconButton(icon=ft.Icons.ARROW_BACK, icon_color=AppTheme.TEXT_ON_PRIMARY, icon_size=24, on_click=lambda e: self.go_back_to_home()),
                        ft.Icon(ft.Icons.HOW_TO_REG, color=AppTheme.TEXT_ON_PRIMARY, size=28),
                        ft.Text("출석 관리", size=22, weight=ft.FontWeight.BOLD, color=AppTheme.TEXT_ON_PRIMARY),
                    ], spacing=8),
                    ft.Container(height=16),
                    ft.Row([
                        ft.Container(
                            content=ft.Row([
                                ft.Icon(ft.Icons.CALENDAR_TODAY, size=18, color=AppTheme.TEXT_ON_PRIMARY),
                                self.attendance_date_text,
                            ], spacing=8),
                            bgcolor=ft.Colors.with_opacity(0.2, ft.Colors.WHITE),
                            padding=ft.padding.symmetric(horizontal=16, vertical=10),
                            border_radius=12,
                            on_click=lambda e: date_picker.pick_date(),
                        ),
                        ft.Container(expand=True),
                        ft.Column([
                            self.attendance_count_text,
                            ft.Text("출석", size=12, color=ft.Colors.with_opacity(0.8, AppTheme.TEXT_ON_PRIMARY)),
                        ], horizontal_alignment=ft.CrossAxisAlignment.CENTER),
                    ]),
                ]),
                padding=ft.padding.only(left=24, right=24, top=48, bottom=24),
                bgcolor=AppTheme.PRIMARY,
                border_radius=ft.border_radius.only(bottom_left=32, bottom_right=32),
            ),

            ft.Container(
                content=ft.Row([
                    ft.Text(f"출석 인원: {MIN_ATTENDANCE}~{MAX_ATTENDANCE}명", size=13, color=AppTheme.WARNING),
                    ft.Container(expand=True),
                    ft.TextButton(
                        "월별 통계",
                        icon=ft.Icons.BAR_CHART,
                        on_click=self.show_monthly_attendance_stats,
                    ),
                ]),
                padding=ft.padding.symmetric(horizontal=20, vertical=8),
            ),

            self.attendance_list,

            ft.Container(
                content=create_primary_button("출석 저장", ft.Icons.SAVE, self.save_attendance, width=200),
                padding=20,
                alignment=ft.Alignment(0, 0),
            ),
        ], spacing=0, expand=True)

        self.tab_content.content = content
        self.page.update()

    def on_attendance_date_change(self, e):
        if e.control.value:
            self.attendance_date = e.control.value.strftime("%Y-%m-%d")
            self.attendance_date_text.value = self.attendance_date
            self.load_attendance_for_date()
            self.page.update()

    def load_attendance_for_date(self):
        self.attendance_checks = {}
        existing = None
        for att in self.attendance.get("attendance", []):
            if att["date"] == self.attendance_date:
                existing = att
                break

        self.attendance_list.controls.clear()
        for member in self.members.get("members", []):
            is_checked = existing and member["id"] in existing.get("member_ids", [])
            self.attendance_checks[member["id"]] = is_checked

            checkbox = ft.Container(
                content=ft.Row([
                    ft.Container(
                        content=ft.Text(member["name"][0], size=16, weight=ft.FontWeight.BOLD,
                                        color=AppTheme.TEXT_ON_PRIMARY if is_checked else AppTheme.PRIMARY),
                        width=40,
                        height=40,
                        bgcolor=AppTheme.PRIMARY if is_checked else AppTheme.ACCENT,
                        border_radius=20,
                        alignment=ft.Alignment(0, 0),
                    ),
                    ft.Text(member["name"], size=15, color=AppTheme.TEXT_PRIMARY, expand=True),
                    ft.Checkbox(
                        value=is_checked,
                        active_color=AppTheme.PRIMARY,
                        on_change=lambda e, mid=member["id"]: self.on_attendance_check(mid, e.control.value),
                    ),
                ], spacing=12),
                padding=12,
                bgcolor=AppTheme.BG_CARD,
                border_radius=12,
                border=ft.border.all(2, AppTheme.PRIMARY) if is_checked else ft.border.all(1, ft.Colors.with_opacity(0.1, ft.Colors.BLACK)),
            )
            self.attendance_list.controls.append(checkbox)

        self.update_attendance_count()

    def on_attendance_check(self, member_id: str, checked: bool):
        self.attendance_checks[member_id] = checked
        self.update_attendance_count()
        self.page.update()

    def update_attendance_count(self):
        count = sum(1 for checked in self.attendance_checks.values() if checked)
        self.attendance_count_text.value = f"{count}명"
        if MIN_ATTENDANCE <= count <= MAX_ATTENDANCE:
            self.attendance_count_text.color = AppTheme.TEXT_ON_PRIMARY
        else:
            self.attendance_count_text.color = AppTheme.SECONDARY

    def show_monthly_attendance_stats(self, e):
        """월별 출석률 통계 표시"""
        today = datetime.now()
        current_month = today.strftime("%Y-%m")

        # 이번 달 운영일 계산 (목요일, 일요일)
        month_start = today.replace(day=1)
        if today.month == 12:
            next_month = today.replace(year=today.year + 1, month=1, day=1)
        else:
            next_month = today.replace(month=today.month + 1, day=1)

        operation_days = []
        current = month_start
        while current < next_month and current <= today:
            if current.weekday() in [3, 6]:  # 목요일(3), 일요일(6)
                operation_days.append(current.strftime("%Y-%m-%d"))
            current += timedelta(days=1)

        total_days = len(operation_days)

        # 회원별 출석 횟수 계산
        member_attendance = {}
        for member in self.members.get("members", []):
            member_attendance[member["id"]] = {"name": member["name"], "count": 0}

        for att in self.attendance.get("attendance", []):
            if att["date"].startswith(current_month):
                for mid in att.get("member_ids", []):
                    if mid in member_attendance:
                        member_attendance[mid]["count"] += 1

        # 출석률 순으로 정렬
        stats = sorted(member_attendance.values(), key=lambda x: x["count"], reverse=True)

        # 통계 리스트 생성
        stats_list = ft.ListView(height=400, spacing=8)
        for stat in stats:
            rate = (stat["count"] / total_days * 100) if total_days > 0 else 0
            stats_list.controls.append(
                ft.Container(
                    content=ft.Row([
                        ft.Container(
                            content=ft.Text(stat["name"][0], size=14, weight=ft.FontWeight.BOLD, color=AppTheme.TEXT_ON_PRIMARY),
                            width=36,
                            height=36,
                            bgcolor=AppTheme.PRIMARY,
                            border_radius=18,
                            alignment=ft.Alignment(0, 0),
                        ),
                        ft.Text(stat["name"], size=14, color=AppTheme.TEXT_PRIMARY, expand=True),
                        ft.Text(f"{stat['count']}/{total_days}", size=14, color=AppTheme.TEXT_SECONDARY),
                        ft.Container(
                            content=ft.Text(f"{rate:.0f}%", size=14, weight=ft.FontWeight.BOLD,
                                          color=AppTheme.SUCCESS if rate >= 75 else AppTheme.WARNING if rate >= 50 else AppTheme.ERROR),
                            width=50,
                            alignment=ft.Alignment(1, 0),
                        ),
                    ], spacing=12),
                    padding=12,
                    bgcolor=AppTheme.BG_CARD,
                    border_radius=10,
                )
            )

        dialog = ft.AlertDialog(
            title=ft.Text(f"{today.strftime('%Y년 %m월')} 출석률", weight=ft.FontWeight.BOLD),
            content=ft.Container(
                content=ft.Column([
                    ft.Row([
                        ft.Icon(ft.Icons.CALENDAR_TODAY, size=18, color=AppTheme.PRIMARY),
                        ft.Text(f"운영일: {total_days}일", size=14, color=AppTheme.TEXT_SECONDARY),
                    ], spacing=8),
                    ft.Container(height=8),
                    stats_list,
                ], tight=True),
                width=320,
                height=450,
            ),
            actions=[
                ft.TextButton("닫기", on_click=lambda e: self.page.close(dialog)),
            ],
            shape=ft.RoundedRectangleBorder(radius=20),
        )
        self.page.open(dialog)

    def save_attendance(self, e):
        checked_ids = [mid for mid, checked in self.attendance_checks.items() if checked]

        if len(checked_ids) < MIN_ATTENDANCE:
            self.page.open(ft.SnackBar(content=ft.Text(f"최소 {MIN_ATTENDANCE}명이 필요합니다."), bgcolor=AppTheme.ERROR))
            self.page.update()
            return

        if len(checked_ids) > MAX_ATTENDANCE:
            self.page.open(ft.SnackBar(content=ft.Text(f"최대 {MAX_ATTENDANCE}명까지 가능합니다."), bgcolor=AppTheme.ERROR))
            self.page.update()
            return

        found = False
        for att in self.attendance.get("attendance", []):
            if att["date"] == self.attendance_date:
                att["member_ids"] = checked_ids
                found = True
                break

        if not found:
            self.attendance["attendance"].append({
                "date": self.attendance_date,
                "member_ids": checked_ids
            })

        save_json(ATTENDANCE_FILE, self.attendance)
        self.page.open(ft.SnackBar(content=ft.Text(f"출석이 저장되었습니다. ({len(checked_ids)}명)"), bgcolor=AppTheme.SUCCESS))
        self.page.update()

    # ==================== 경기 탭 ====================
    def show_match_tab(self):
        self.match_date = datetime.now().strftime("%Y-%m-%d")

        match_date_picker = ft.DatePicker(
            on_change=self.on_match_date_change,
            first_date=datetime(2024, 1, 1),
            last_date=datetime(2030, 12, 31),
        )
        self.page.overlay.append(match_date_picker)

        self.match_date_text = ft.Text(self.match_date, size=16, weight=ft.FontWeight.BOLD, color=AppTheme.TEXT_ON_PRIMARY)
        self.match_results_list = ft.ListView(expand=True, spacing=0, padding=ft.padding.symmetric(horizontal=20))

        self.update_match_results_list()

        content = ft.Column([
            ft.Container(
                content=ft.Column([
                    ft.Row([
                        ft.IconButton(icon=ft.Icons.ARROW_BACK, icon_color=AppTheme.TEXT_ON_PRIMARY, icon_size=24, on_click=lambda e: self.go_back_to_home()),
                        ft.Icon(ft.Icons.SPORTS_TENNIS, color=AppTheme.TEXT_ON_PRIMARY, size=28),
                        ft.Text("경기 관리", size=22, weight=ft.FontWeight.BOLD, color=AppTheme.TEXT_ON_PRIMARY),
                    ], spacing=8),
                    ft.Container(height=16),
                    ft.Container(
                        content=ft.Row([
                            ft.Icon(ft.Icons.CALENDAR_TODAY, size=18, color=AppTheme.TEXT_ON_PRIMARY),
                            self.match_date_text,
                        ], spacing=8),
                        bgcolor=ft.Colors.with_opacity(0.2, ft.Colors.WHITE),
                        padding=ft.padding.symmetric(horizontal=16, vertical=10),
                        border_radius=12,
                        on_click=lambda e: match_date_picker.pick_date(),
                    ),
                ]),
                padding=ft.padding.only(left=24, right=24, top=48, bottom=24),
                bgcolor=AppTheme.PRIMARY,
                border_radius=ft.border_radius.only(bottom_left=32, bottom_right=32),
            ),

            ft.Container(
                content=ft.Row([
                    create_primary_button("자동 매칭", ft.Icons.AUTO_AWESOME, self.show_auto_match_dialog),
                    ft.Container(width=12),
                    create_secondary_button("수동 입력", ft.Icons.EDIT, self.show_add_match_dialog),
                ]),
                padding=ft.padding.symmetric(horizontal=20, vertical=16),
            ),

            ft.Container(
                content=ft.Row([
                    ft.Text("경기 결과", size=16, weight=ft.FontWeight.BOLD, color=AppTheme.TEXT_PRIMARY),
                    ft.Container(expand=True),
                    ft.IconButton(
                        icon=ft.Icons.REFRESH,
                        icon_color=AppTheme.PRIMARY,
                        icon_size=22,
                        tooltip="새로고침",
                        on_click=lambda e: self._refresh_match_tab(),
                    ),
                ]),
                padding=ft.padding.symmetric(horizontal=20),
            ),

            self.match_results_list,
        ], spacing=0, expand=True)

        self.tab_content.content = content
        self.page.update()

    def _refresh_match_tab(self):
        """경기 탭 데이터 새로고침"""
        self.reload_data()
        self.update_match_results_list()
        self.page.open(ft.SnackBar(content=ft.Text("데이터를 새로고침했습니다."), bgcolor=AppTheme.SUCCESS))
        self.page.update()

    def on_match_date_change(self, e):
        if e.control.value:
            self.match_date = e.control.value.strftime("%Y-%m-%d")
            self.match_date_text.value = self.match_date
            self.update_match_results_list()
            self.page.update()

    def get_attendance_for_date(self, date: str) -> List[str]:
        for att in self.attendance.get("attendance", []):
            if att["date"] == date:
                return att.get("member_ids", [])
        return []

    def _build_match_list_controls(self, match_list):
        """자동 매칭 결과를 ListView에 추가"""
        match_list.controls.clear()
        current_slot = 0
        for match in self.auto_match_schedule:
            time_slot = match.get("time_slot", 0)
            start_time = match.get("start_time", "")
            court = match.get("court", "")
            team1_names = self.get_member_names(match["team1"])
            team2_names = self.get_member_names(match["team2"])

            # 타임슬롯 구분선 (시작시간 표시)
            if time_slot != current_slot:
                current_slot = time_slot
                time_label = f"── {time_slot}타임 {start_time} ──" if start_time else f"── {time_slot}타임 ──"
                match_list.controls.append(
                    ft.Container(
                        content=ft.Text(time_label,
                                        size=13, weight=ft.FontWeight.BOLD,
                                        color=AppTheme.PRIMARY, text_align=ft.TextAlign.CENTER),
                        padding=ft.padding.only(top=8, bottom=4),
                        alignment=ft.Alignment(0, 0),
                    )
                )

            match_list.controls.append(
                ft.Container(
                    content=ft.Row([
                        ft.Container(
                            content=ft.Text(court, size=11, weight=ft.FontWeight.BOLD, color=AppTheme.TEXT_ON_PRIMARY),
                            bgcolor=AppTheme.PRIMARY_LIGHT,
                            padding=ft.padding.symmetric(horizontal=8, vertical=4),
                            border_radius=8,
                        ),
                        ft.Text(team1_names, size=13, color=AppTheme.TEXT_PRIMARY, expand=True),
                        ft.Text("vs", size=12, color=AppTheme.TEXT_SECONDARY),
                        ft.Text(team2_names, size=13, color=AppTheme.TEXT_PRIMARY, expand=True, text_align=ft.TextAlign.RIGHT),
                    ], spacing=8),
                    padding=12,
                    bgcolor=AppTheme.BG_CARD,
                    border_radius=10,
                )
            )

    def show_auto_match_dialog(self, e):
        attendees = self.get_attendance_for_date(self.match_date)

        if len(attendees) < MIN_ATTENDANCE:
            self.page.open(ft.SnackBar(
                content=ft.Text(f"출석자 부족 (현재: {len(attendees)}명, 최소: {MIN_ATTENDANCE}명)"),
                bgcolor=AppTheme.ERROR
            ))
            self.page.update()
            return

        # 경기 날짜의 요일에 맞는 스케줄 사용
        try:
            match_dt = datetime.strptime(self.match_date, "%Y-%m-%d")
            day_name = ["월", "화", "수", "목", "금", "토", "일"][match_dt.weekday()]
            schedule = SCHEDULE.get(day_name, SCHEDULE["목"])
        except Exception:
            schedule = get_today_schedule()

        self.auto_match_schedule = generate_random_matches(attendees, schedule=schedule)
        total_matches = len(self.auto_match_schedule)
        num_slots = len(schedule["times"])

        match_list = ft.ListView(height=380, spacing=4)
        self._build_match_list_controls(match_list)

        def confirm_auto_match(e):
            self.page.close(dialog)
            self.show_auto_match_score_input()

        def regenerate_matches(e):
            self.auto_match_schedule = generate_random_matches(attendees, schedule=schedule)
            self._build_match_list_controls(match_list)
            self.page.update()

        dialog = ft.AlertDialog(
            title=ft.Text(f"자동 매칭 ({total_matches}경기 · {NUM_COURTS}코트)", weight=ft.FontWeight.BOLD),
            content=ft.Container(
                content=ft.Column([
                    ft.Row([
                        ft.Icon(ft.Icons.PEOPLE, size=18, color=AppTheme.PRIMARY),
                        ft.Text(f"출석자: {len(attendees)}명", size=14, color=AppTheme.TEXT_SECONDARY),
                        ft.Container(width=8),
                        ft.Icon(ft.Icons.SCHEDULE, size=18, color=AppTheme.SECONDARY),
                        ft.Text(f"{num_slots}타임 · {', '.join(COURT_NAMES)}", size=14, color=AppTheme.TEXT_SECONDARY),
                    ], spacing=4),
                    ft.Container(height=4),
                    match_list,
                ], tight=True),
                width=380,
                height=440,
            ),
            actions=[
                ft.TextButton("다시 추첨", on_click=regenerate_matches),
                ft.TextButton("취소", on_click=lambda e: self.page.close(dialog)),
                create_primary_button("확정", on_click=confirm_auto_match),
            ],
            shape=ft.RoundedRectangleBorder(radius=20),
        )
        self.page.open(dialog)

    def show_auto_match_score_input(self):
        self.score_inputs = []
        score_list = ft.ListView(expand=True, spacing=12, padding=ft.padding.symmetric(horizontal=20))

        current_slot = 0
        for match in self.auto_match_schedule:
            time_slot = match.get("time_slot", 0)
            start_time = match.get("start_time", "")
            court = match.get("court", "")
            team1_names = self.get_member_names(match["team1"])
            team2_names = self.get_member_names(match["team2"])

            # 타임슬롯 구분선 (시작시간 포함)
            if time_slot != current_slot:
                current_slot = time_slot
                time_label = f"── {time_slot}타임 {start_time} ──" if start_time else f"── {time_slot}타임 ──"
                score_list.controls.append(
                    ft.Container(
                        content=ft.Text(time_label,
                                        size=14, weight=ft.FontWeight.BOLD,
                                        color=AppTheme.PRIMARY, text_align=ft.TextAlign.CENTER),
                        padding=ft.padding.only(top=12, bottom=4),
                        alignment=ft.Alignment(0, 0),
                    )
                )

            score1_field = ft.TextField(
                width=70,
                text_align=ft.TextAlign.CENTER,
                keyboard_type=ft.KeyboardType.NUMBER,
                border_radius=10,
                text_size=24,
                border_color=AppTheme.PRIMARY_LIGHT,
            )
            score2_field = ft.TextField(
                width=70,
                text_align=ft.TextAlign.CENTER,
                keyboard_type=ft.KeyboardType.NUMBER,
                border_radius=10,
                text_size=24,
                border_color=AppTheme.PRIMARY_LIGHT,
            )

            self.score_inputs.append({
                "match": match,
                "score1": score1_field,
                "score2": score2_field,
            })

            score_list.controls.append(
                ft.Container(
                    content=ft.Column([
                        ft.Row([
                            ft.Container(
                                content=ft.Text(court, size=13, weight=ft.FontWeight.BOLD, color=AppTheme.TEXT_ON_PRIMARY),
                                bgcolor=AppTheme.PRIMARY_LIGHT,
                                padding=ft.padding.symmetric(horizontal=12, vertical=6),
                                border_radius=8,
                            ),
                        ]),
                        ft.Container(height=8),
                        ft.Row([
                            ft.Column([
                                ft.Text(team1_names, size=13, color=AppTheme.TEXT_PRIMARY, text_align=ft.TextAlign.CENTER),
                                ft.Container(height=4),
                                score1_field,
                            ], horizontal_alignment=ft.CrossAxisAlignment.CENTER, expand=True),
                            ft.Text(":", size=28, color=AppTheme.TEXT_SECONDARY),
                            ft.Column([
                                ft.Text(team2_names, size=13, color=AppTheme.TEXT_PRIMARY, text_align=ft.TextAlign.CENTER),
                                ft.Container(height=4),
                                score2_field,
                            ], horizontal_alignment=ft.CrossAxisAlignment.CENTER, expand=True),
                        ], alignment=ft.MainAxisAlignment.CENTER),
                    ]),
                    padding=16,
                    bgcolor=AppTheme.BG_CARD,
                    border_radius=16,
                    shadow=AppTheme.CARD_SHADOW,
                )
            )

        content = ft.Column([
            create_header_card("경기 결과 입력", self.match_date, ft.Icons.EDIT_NOTE, lambda e: self.show_match_tab()),
            score_list,
            ft.Container(
                content=ft.Row([
                    create_secondary_button("취소", on_click=lambda e: self.show_match_tab()),
                    ft.Container(width=12),
                    create_primary_button("모두 저장", ft.Icons.SAVE, self.save_all_auto_matches),
                ], alignment=ft.MainAxisAlignment.CENTER),
                padding=20,
            ),
        ], spacing=0, expand=True)

        self.tab_content.content = content
        self.page.update()

    def save_all_auto_matches(self, e):
        saved_count = 0

        for item in self.score_inputs:
            try:
                score1 = int(item["score1"].value) if item["score1"].value else None
                score2 = int(item["score2"].value) if item["score2"].value else None

                if score1 is not None and score2 is not None:
                    match = item["match"]
                    # 무승부 처리
                    if score1 == score2:
                        winner = "draw"
                    else:
                        winner = "team1" if score1 > score2 else "team2"

                    new_match = {
                        "id": generate_id("g"),
                        "date": self.match_date,
                        "team1": match["team1"],
                        "team2": match["team2"],
                        "score1": score1,
                        "score2": score2,
                        "winner": winner,
                        "court": match.get("court", ""),
                        "time_slot": match.get("time_slot", 0),
                        "start_time": match.get("start_time", ""),
                        "recorded_by": self.current_user or "",
                    }
                    self.matches["matches"].append(new_match)
                    saved_count += 1
            except (ValueError, TypeError):
                continue

        if saved_count > 0:
            save_json(MATCHES_FILE, self.matches)
            self.page.open(ft.SnackBar(content=ft.Text(f"{saved_count}개 경기가 저장되었습니다."), bgcolor=AppTheme.SUCCESS))
        else:
            self.page.open(ft.SnackBar(content=ft.Text("저장할 경기가 없습니다."), bgcolor=AppTheme.WARNING))

        self.show_match_tab()

    def update_match_results_list(self):
        self.match_results_list.controls.clear()
        day_matches = [m for m in self.matches.get("matches", []) if m["date"] == self.match_date]

        if not day_matches:
            self.match_results_list.controls.append(
                ft.Container(
                    content=ft.Column([
                        ft.Icon(ft.Icons.SPORTS_TENNIS, size=48, color=AppTheme.TEXT_SECONDARY),
                        ft.Text("경기 기록이 없습니다", color=AppTheme.TEXT_SECONDARY),
                    ], horizontal_alignment=ft.CrossAxisAlignment.CENTER, spacing=12),
                    padding=40,
                    alignment=ft.Alignment(0, 0),
                )
            )
        else:
            for i, match in enumerate(day_matches):
                team1_names = self.get_member_names(match["team1"])
                team2_names = self.get_member_names(match["team2"])
                self.match_results_list.controls.append(
                    create_match_result_card(
                        i + 1,
                        team1_names,
                        team2_names,
                        match["score1"],
                        match["score2"],
                        on_delete=lambda e, m=match: self.delete_match(m),
                        court=match.get("court", ""),
                        time_slot=match.get("time_slot", 0),
                        start_time=match.get("start_time", ""),
                    )
                )

    def get_member_names(self, member_ids: list) -> str:
        names = []
        for mid in member_ids:
            for member in self.members.get("members", []):
                if member["id"] == mid:
                    names.append(member["name"])
                    break
        return " & ".join(names) if names else "알 수 없음"

    def get_member_name(self, member_id: str) -> str:
        for member in self.members.get("members", []):
            if member["id"] == member_id:
                return member["name"]
        return "알 수 없음"

    def show_add_match_dialog(self, e):
        attendees = self.get_attendance_for_date(self.match_date)
        if attendees:
            members_list = [m for m in self.members.get("members", []) if m["id"] in attendees]
        else:
            members_list = self.members.get("members", [])

        if len(members_list) < 4:
            self.page.open(ft.SnackBar(content=ft.Text("최소 4명의 회원이 필요합니다."), bgcolor=AppTheme.ERROR))
            return

        member_options = [ft.dropdown.Option(m["id"], m["name"]) for m in members_list]

        team1_player1 = ft.Dropdown(label="팀1 선수1", options=member_options.copy(), width=140, border_radius=10)
        team1_player2 = ft.Dropdown(label="팀1 선수2", options=member_options.copy(), width=140, border_radius=10)
        team2_player1 = ft.Dropdown(label="팀2 선수1", options=member_options.copy(), width=140, border_radius=10)
        team2_player2 = ft.Dropdown(label="팀2 선수2", options=member_options.copy(), width=140, border_radius=10)

        score1_field = ft.TextField(label="팀1", width=70, keyboard_type=ft.KeyboardType.NUMBER, border_radius=10)
        score2_field = ft.TextField(label="팀2", width=70, keyboard_type=ft.KeyboardType.NUMBER, border_radius=10)

        def save_match(e):
            if not all([team1_player1.value, team1_player2.value, team2_player1.value, team2_player2.value]):
                self.page.open(ft.SnackBar(content=ft.Text("모든 선수를 선택해주세요."), bgcolor=AppTheme.ERROR))
                return

            selected = [team1_player1.value, team1_player2.value, team2_player1.value, team2_player2.value]
            if len(set(selected)) != 4:
                self.page.open(ft.SnackBar(content=ft.Text("중복된 선수가 있습니다."), bgcolor=AppTheme.ERROR))
                return

            try:
                score1 = int(score1_field.value)
                score2 = int(score2_field.value)
            except (ValueError, TypeError):
                self.page.open(ft.SnackBar(content=ft.Text("점수를 올바르게 입력해주세요."), bgcolor=AppTheme.ERROR))
                return

            # 무승부 처리
            if score1 == score2:
                winner = "draw"
            else:
                winner = "team1" if score1 > score2 else "team2"

            new_match = {
                "id": generate_id("g"),
                "date": self.match_date,
                "team1": [team1_player1.value, team1_player2.value],
                "team2": [team2_player1.value, team2_player2.value],
                "score1": score1,
                "score2": score2,
                "winner": winner,
                "recorded_by": self.current_user or "",
            }
            self.matches["matches"].append(new_match)
            save_json(MATCHES_FILE, self.matches)

            self.page.close(dialog)
            self.show_match_tab()

        dialog = ft.AlertDialog(
            title=ft.Text("경기 결과 입력", weight=ft.FontWeight.BOLD),
            content=ft.Container(
                content=ft.Column([
                    ft.Text("팀1", weight=ft.FontWeight.BOLD, color=AppTheme.PRIMARY),
                    ft.Row([team1_player1, team1_player2], wrap=True),
                    ft.Container(height=8),
                    ft.Text("팀2", weight=ft.FontWeight.BOLD, color=AppTheme.PRIMARY),
                    ft.Row([team2_player1, team2_player2], wrap=True),
                    ft.Divider(),
                    ft.Text("점수", weight=ft.FontWeight.BOLD, color=AppTheme.PRIMARY),
                    ft.Row([score1_field, ft.Text(":", size=24), score2_field], alignment=ft.MainAxisAlignment.CENTER),
                ], tight=True, spacing=8),
                width=320,
            ),
            actions=[
                ft.TextButton("취소", on_click=lambda e: self.page.close(dialog)),
                create_primary_button("저장", on_click=save_match),
            ],
            shape=ft.RoundedRectangleBorder(radius=20),
        )
        self.page.open(dialog)

    def delete_match(self, match: dict):
        def confirm_delete(e):
            self.matches["matches"] = [m for m in self.matches["matches"] if m["id"] != match["id"]]
            save_json(MATCHES_FILE, self.matches)
            self.page.close(dialog)
            self.show_match_tab()

        dialog = ft.AlertDialog(
            title=ft.Text("경기 삭제", weight=ft.FontWeight.BOLD),
            content=ft.Text("이 경기 기록을 삭제하시겠습니까?"),
            actions=[
                ft.TextButton("취소", on_click=lambda e: self.page.close(dialog)),
                ft.ElevatedButton("삭제", on_click=confirm_delete, bgcolor=AppTheme.ERROR, color=AppTheme.TEXT_ON_PRIMARY),
            ],
            shape=ft.RoundedRectangleBorder(radius=20),
        )
        self.page.open(dialog)

    # ==================== 순위 탭 ====================
    def show_ranking_tab(self):
        self.ranking_type = "weekly"
        self.ranking_list = ft.ListView(expand=True, spacing=0, padding=ft.padding.symmetric(horizontal=20))

        content = ft.Column([
            create_header_card("순위", "실력을 겨루세요!", ft.Icons.EMOJI_EVENTS, lambda e: self.go_back_to_home()),
            ft.Container(
                content=ft.SegmentedButton(
                    selected={self.ranking_type},
                    on_change=self.on_ranking_type_change,
                    style=ft.ButtonStyle(
                        shape=ft.RoundedRectangleBorder(radius=12),
                    ),
                    segments=[
                        ft.Segment(value="daily", label=ft.Text("오늘")),
                        ft.Segment(value="weekly", label=ft.Text("주간")),
                        ft.Segment(value="monthly", label=ft.Text("월간")),
                    ],
                ),
                padding=ft.padding.symmetric(horizontal=20, vertical=12),
            ),
            self.ranking_list,
        ], spacing=0, expand=True)

        self.update_ranking_list()
        self.tab_content.content = content
        self.page.update()

    def on_ranking_type_change(self, e):
        self.ranking_type = list(e.control.selected)[0]
        self.update_ranking_list()
        self.page.update()

    def calculate_rankings(self, start_date: datetime, end_date: datetime) -> list:
        scores = {}

        for match in self.matches.get("matches", []):
            match_date = datetime.strptime(match["date"], "%Y-%m-%d")
            if start_date <= match_date <= end_date:
                team1 = match["team1"]
                team2 = match["team2"]
                score1 = match["score1"]
                score2 = match["score2"]
                winner = match.get("winner", "")
                is_draw = winner == "draw" or score1 == score2
                is_team1_winner = winner == "team1"
                is_team2_winner = winner == "team2"
                game_diff = abs(score1 - score2)

                for player_id in team1:
                    if player_id not in scores:
                        scores[player_id] = {"wins": 0, "losses": 0, "draws": 0, "points": 0, "games_won": 0, "games_lost": 0}
                    scores[player_id]["games_won"] += score1
                    scores[player_id]["games_lost"] += score2
                    if is_draw:
                        scores[player_id]["draws"] += 1
                        scores[player_id]["points"] += 1  # 무승부는 1점
                    elif is_team1_winner:
                        scores[player_id]["wins"] += 1
                        scores[player_id]["points"] += 2 + game_diff
                    else:
                        scores[player_id]["losses"] += 1
                        scores[player_id]["points"] -= game_diff

                for player_id in team2:
                    if player_id not in scores:
                        scores[player_id] = {"wins": 0, "losses": 0, "draws": 0, "points": 0, "games_won": 0, "games_lost": 0}
                    scores[player_id]["games_won"] += score2
                    scores[player_id]["games_lost"] += score1
                    if is_draw:
                        scores[player_id]["draws"] += 1
                        scores[player_id]["points"] += 1  # 무승부는 1점
                    elif is_team2_winner:
                        scores[player_id]["wins"] += 1
                        scores[player_id]["points"] += 2 + game_diff
                    else:
                        scores[player_id]["losses"] += 1
                        scores[player_id]["points"] -= game_diff

        rankings = []
        for player_id, data in scores.items():
            name = self.get_member_name(player_id)
            rankings.append({
                "id": player_id,
                "name": name,
                "points": data["points"],
                "wins": data["wins"],
                "losses": data["losses"],
                "draws": data["draws"],
                "games_won": data["games_won"],
                "games_lost": data["games_lost"],
            })

        rankings.sort(key=lambda x: x["points"], reverse=True)
        return rankings

    def update_ranking_list(self):
        self.ranking_list.controls.clear()
        today = datetime.now()

        if self.ranking_type == "daily":
            start_date = today.replace(hour=0, minute=0, second=0, microsecond=0)
            end_date = today.replace(hour=23, minute=59, second=59)
            period_text = f"오늘 ({today.strftime('%m/%d')})"
        elif self.ranking_type == "weekly":
            start_date, end_date = get_week_range(today)
            period_text = f"이번 주 ({start_date.strftime('%m/%d')} ~ {end_date.strftime('%m/%d')})"
        else:
            start_date, end_date = get_month_range(today)
            period_text = f"이번 달 ({today.strftime('%Y년 %m월')})"

        self.ranking_list.controls.append(
            ft.Container(
                content=ft.Text(period_text, size=14, color=AppTheme.TEXT_SECONDARY),
                padding=ft.padding.only(bottom=12),
            )
        )

        rankings = self.calculate_rankings(start_date, end_date)

        if not rankings:
            self.ranking_list.controls.append(
                ft.Container(
                    content=ft.Column([
                        ft.Icon(ft.Icons.EMOJI_EVENTS, size=48, color=AppTheme.TEXT_SECONDARY),
                        ft.Text("경기 기록이 없습니다", color=AppTheme.TEXT_SECONDARY),
                    ], horizontal_alignment=ft.CrossAxisAlignment.CENTER, spacing=12),
                    padding=40,
                    alignment=ft.Alignment(0, 0),
                )
            )
        else:
            for i, player in enumerate(rankings):
                self.ranking_list.controls.append(
                    create_ranking_card(
                        i + 1,
                        player["name"],
                        player["points"],
                        player["wins"],
                        player["losses"],
                        player["games_won"],
                        player["games_lost"],
                        player.get("draws", 0),
                    )
                )

    # ==================== 설정 탭 ====================
    def show_settings_tab(self):
        content = ft.Column([
            create_header_card("설정", "앱 설정 및 데이터 관리", ft.Icons.SETTINGS, lambda e: self.go_back_to_home()),

            ft.Container(
                content=ft.Column([
                    create_styled_card(
                        ft.Column([
                            ft.Row([
                                ft.Icon(ft.Icons.CLOUD_UPLOAD, color=AppTheme.PRIMARY, size=24),
                                ft.Text("데이터 관리", size=16, weight=ft.FontWeight.BOLD, color=AppTheme.TEXT_PRIMARY),
                            ], spacing=10),
                            ft.Text("JSON 파일로 데이터를 내보내거나 불러와서\n다른 기기와 동기화할 수 있습니다.",
                                   size=13, color=AppTheme.TEXT_SECONDARY),
                            ft.Container(height=12),
                            ft.Row([
                                create_primary_button("내보내기", ft.Icons.UPLOAD, self.export_data),
                                ft.Container(width=12),
                                create_secondary_button("불러오기", ft.Icons.DOWNLOAD, self.import_data),
                            ]),
                        ], spacing=8),
                        padding=20,
                    ),

                    create_styled_card(
                        ft.Column([
                            ft.Row([
                                ft.Icon(ft.Icons.ANALYTICS, color=AppTheme.PRIMARY, size=24),
                                ft.Text("데이터 현황", size=16, weight=ft.FontWeight.BOLD, color=AppTheme.TEXT_PRIMARY),
                            ], spacing=10),
                            ft.Container(height=8),
                            ft.Row([
                                create_stat_box(str(len(self.members.get('members', []))), "회원"),
                                ft.Container(width=8),
                                create_stat_box(str(len(self.attendance.get('attendance', []))), "출석일"),
                                ft.Container(width=8),
                                create_stat_box(str(len(self.matches.get('matches', []))), "경기"),
                            ]),
                        ], spacing=8),
                        padding=20,
                    ),

                    ft.Container(
                        content=ft.Column([
                            ft.Row([
                                ft.Icon(ft.Icons.WARNING, color=AppTheme.ERROR, size=24),
                                ft.Text("위험 구역", size=16, weight=ft.FontWeight.BOLD, color=AppTheme.ERROR),
                            ], spacing=10),
                            ft.Container(height=8),
                            ft.ElevatedButton(
                                "모든 데이터 삭제",
                                icon=ft.Icons.DELETE_FOREVER,
                                on_click=self.confirm_delete_all_data,
                                bgcolor=AppTheme.ERROR,
                                color=AppTheme.TEXT_ON_PRIMARY,
                                style=ft.ButtonStyle(shape=ft.RoundedRectangleBorder(radius=12)),
                            ),
                        ]),
                        padding=20,
                        bgcolor=ft.Colors.with_opacity(0.05, AppTheme.ERROR),
                        border_radius=16,
                        border=ft.border.all(1, ft.Colors.with_opacity(0.2, AppTheme.ERROR)),
                    ),
                ]),
                padding=20,
            ),
        ], spacing=0, scroll=ft.ScrollMode.AUTO, expand=True)

        self.tab_content.content = content
        self.page.update()

    def export_data(self, e):
        export_data = {
            "club_name": "서초 채널",
            "export_date": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "members": self.members,
            "attendance": self.attendance,
            "matches": self.matches,
        }

        export_file = os.path.join(DATA_DIR, f"seocho_backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json")
        save_json(export_file, export_data)

        self.page.open(ft.SnackBar(content=ft.Text(f"저장됨: {export_file}"), bgcolor=AppTheme.SUCCESS))
        self.page.update()

    def import_data(self, e):
        def pick_file_result(e: ft.FilePickerResultEvent):
            if e.files and len(e.files) > 0:
                file_path = e.files[0].path
                try:
                    with open(file_path, 'r', encoding='utf-8') as f:
                        import_data = json.load(f)

                    if "members" in import_data:
                        self.members = import_data["members"]
                        save_json(MEMBERS_FILE, self.members)
                    if "attendance" in import_data:
                        self.attendance = import_data["attendance"]
                        save_json(ATTENDANCE_FILE, self.attendance)
                    if "matches" in import_data:
                        self.matches = import_data["matches"]
                        save_json(MATCHES_FILE, self.matches)

                    self.page.open(ft.SnackBar(content=ft.Text("데이터를 불러왔습니다!"), bgcolor=AppTheme.SUCCESS))
                    self.show_settings_tab()
                except Exception as ex:
                    self.page.open(ft.SnackBar(content=ft.Text(f"오류: {str(ex)}"), bgcolor=AppTheme.ERROR))
                self.page.update()

        file_picker = ft.FilePicker(on_result=pick_file_result)
        self.page.overlay.append(file_picker)
        self.page.update()
        file_picker.pick_files(allowed_extensions=["json"], dialog_title="백업 파일 선택")

    def confirm_delete_all_data(self, e):
        def delete_all(e):
            self.members = {"members": []}
            self.attendance = {"attendance": []}
            self.matches = {"matches": []}
            save_json(MEMBERS_FILE, self.members)
            save_json(ATTENDANCE_FILE, self.attendance)
            save_json(MATCHES_FILE, self.matches)
            self.page.close(dialog)
            self.page.open(ft.SnackBar(content=ft.Text("모든 데이터가 삭제되었습니다."), bgcolor=AppTheme.SUCCESS))
            self.show_settings_tab()

        dialog = ft.AlertDialog(
            title=ft.Text("경고", weight=ft.FontWeight.BOLD, color=AppTheme.ERROR),
            content=ft.Text("정말로 모든 데이터를 삭제하시겠습니까?\n이 작업은 되돌릴 수 없습니다."),
            actions=[
                ft.TextButton("취소", on_click=lambda e: self.page.close(dialog)),
                ft.ElevatedButton("삭제", on_click=delete_all, bgcolor=AppTheme.ERROR, color=AppTheme.TEXT_ON_PRIMARY),
            ],
            shape=ft.RoundedRectangleBorder(radius=20),
        )
        self.page.open(dialog)


def main(page: ft.Page):
    TennisClubApp(page)


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8550))
    ft.app(
        target=main,
        view=None,  # 웹 서버 모드 (브라우저 자동 열기 안 함)
        host="0.0.0.0",
        port=port,
        assets_dir="assets",
    )
