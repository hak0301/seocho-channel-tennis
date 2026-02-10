"""
Firebase Realtime Database REST API 모듈
- SDK 없이 requests만으로 CRUD 구현
- 오프라인 시 로컬 JSON 폴백
"""

import requests
import json
import os

# ============================================================
# Firebase 프로젝트 설정 (사용자가 직접 입력)
# ============================================================
# Firebase Console > Realtime Database > URL 복사
FIREBASE_URL = "https://seocho-5e9ea-default-rtdb.asia-southeast1.firebasedatabase.app"

# 연결 타임아웃 (초)
TIMEOUT = 5

# 로컬 캐시 디렉토리
CACHE_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data")


def is_firebase_configured():
    """Firebase URL이 설정되었는지 확인"""
    return bool(FIREBASE_URL and FIREBASE_URL.startswith("https://"))


def _ensure_cache_dir():
    if not os.path.exists(CACHE_DIR):
        os.makedirs(CACHE_DIR)


def _cache_path(path):
    """Firebase path를 로컬 캐시 파일 경로로 변환"""
    safe_name = path.replace("/", "_").strip("_") or "root"
    return os.path.join(CACHE_DIR, f"{safe_name}_cache.json")


def _save_cache(path, data):
    """로컬 캐시에 저장"""
    _ensure_cache_dir()
    try:
        with open(_cache_path(path), 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    except Exception:
        pass


def _load_cache(path, default=None):
    """로컬 캐시에서 로드"""
    cache_file = _cache_path(path)
    if os.path.exists(cache_file):
        try:
            with open(cache_file, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception:
            pass
    return default


def fb_get(path, default=None):
    """Firebase에서 데이터 조회 (GET)"""
    if not is_firebase_configured():
        return _load_cache(path, default)

    try:
        url = f"{FIREBASE_URL}/{path}.json"
        resp = requests.get(url, timeout=TIMEOUT)
        resp.raise_for_status()
        data = resp.json()
        if data is None:
            data = default
        _save_cache(path, data)
        return data
    except Exception:
        return _load_cache(path, default)


def fb_put(path, data):
    """Firebase에 데이터 전체 덮어쓰기 (PUT)"""
    _save_cache(path, data)

    if not is_firebase_configured():
        return True

    try:
        url = f"{FIREBASE_URL}/{path}.json"
        resp = requests.put(url, json=data, timeout=TIMEOUT)
        resp.raise_for_status()
        return True
    except Exception:
        return False


def fb_patch(path, data):
    """Firebase 데이터 부분 업데이트 (PATCH)"""
    if not is_firebase_configured():
        existing = _load_cache(path, {})
        if isinstance(existing, dict):
            existing.update(data)
            _save_cache(path, existing)
        return True

    try:
        url = f"{FIREBASE_URL}/{path}.json"
        resp = requests.patch(url, json=data, timeout=TIMEOUT)
        resp.raise_for_status()
        _save_cache(path, data)
        return True
    except Exception:
        return False


def fb_delete(path):
    """Firebase 데이터 삭제 (DELETE)"""
    cache_file = _cache_path(path)
    if os.path.exists(cache_file):
        try:
            os.remove(cache_file)
        except Exception:
            pass

    if not is_firebase_configured():
        return True

    try:
        url = f"{FIREBASE_URL}/{path}.json"
        resp = requests.delete(url, timeout=TIMEOUT)
        resp.raise_for_status()
        return True
    except Exception:
        return False


def fb_push(path, data):
    """Firebase에 새 항목 추가 (POST) - 고유 키 자동 생성"""
    if not is_firebase_configured():
        existing = _load_cache(path, [])
        if isinstance(existing, list):
            existing.append(data)
            _save_cache(path, existing)
        return True

    try:
        url = f"{FIREBASE_URL}/{path}.json"
        resp = requests.post(url, json=data, timeout=TIMEOUT)
        resp.raise_for_status()
        return True
    except Exception:
        return False
