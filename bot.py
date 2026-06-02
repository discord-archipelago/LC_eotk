"""
림버스 컴퍼니 대사 검색 디스코드 봇
- /대사검색 : 스토리 대사 검색
- /설명검색 : 인격/스킬/EGO 등 설명 검색
"""

import os
import random
import re
import discord
from discord import app_commands
from discord.ext import commands
import json
from pathlib import Path
from typing import Optional, List, Dict
from dotenv import load_dotenv

load_dotenv()

# ──────────────────────────────────────────
BASE_DIR       = Path(__file__).parent
KR_DIR         = BASE_DIR / "KR_json"
VOICE_DIR      = BASE_DIR / "json"
DTALE_KR_DIR   = BASE_DIR / "Dtales_KRjson"
DTALE_V_DIR    = BASE_DIR / "Dtales_json"
MISC_DIR       = BASE_DIR / "Misc_KRjson"
# ──────────────────────────────────────────

RESULTS_PER_PAGE = 5

# ★ 여기에 원하는 문장 추가하면 됨
FOOTER_MESSAGES = [
    "림버스 컴퍼니의 수석 연구원 호엔하임(이 키우는 벌레)라는 컨셉으로 만든 대사 검색 봇입니다 !!",
    "두루지벌레가 대사를 찾는 중이군",
    "집가고싶다",
    "추가하고싶은 대사 / 기능이 있다면 히원의 dm으로",
    "봇이 두루지벌레인 이유는 호엔하임을 닮아서라고..",
    "음성파일은 구드에서 검색할 수 있다네",
    "팀장님 저 벌레는 어디서 데려온거에요",
    "이상적인 벌레구료",
    "흠..",
    "아아. 마이크 테스트.",
    "130",
    "팀장님? 언제 벌레가 되신거죠..?\n..나는 여기 있네만",
    "알리사.. 에프킬라 저리 치우게",
    "두루지벌레의 영문 이름은 blipbug라네",
]

MAIN_CHAPTERS  = {"1","2","3","4","5","6","7","8","9"}
INTER_CHAPTERS = {"3.5","4.5","5.5","6.5","7.5","8.5","9.5"}

search_data: List[Dict] = []
misc_data:   List[Dict] = []


# ── 챕터/카테고리 추출 ────────────────────────
def get_chapter(key: str) -> str:
    m = re.match(r'^(\d+)D', key)
    if m: return m.group(1)
    m = re.match(r'^S(\d)', key)
    if m: return m.group(1)
    return "0"

def get_dtale_chapter(key: str) -> str:
    m = re.match(r'^E([1-9])\d\d', key)
    if m: return f"{m.group(1)}.5"
    return "기타"

def get_misc_category(key: str) -> str:
    if re.match(r'^Announcer', key):              return "어나운서"
    if re.match(r'^AbDlg', key):                  return "선택지대사"
    if re.match(r'^Skills_(personality|Ego)', key): return "스킬설명"
    if re.match(r'^Passives?', key):              return "패시브"
    if re.match(r'^Egos', key):                   return "EGO"
    if re.match(r'^BattleSpeechBubble', key):     return "배틀대사"
    if re.match(r'^BgmLyrics', key):              return "BGM가사"
    if re.match(r'^StoryTheaterDanteNote', key):  return "단테노트"
    return "기타"


# ── 스토리 데이터 로드 ───────────────────────
def load_all_data():
    search_data.clear()
    for kr_file in sorted(KR_DIR.glob("KR_*.json")):
        key = kr_file.stem[3:]
        _load_story_file(kr_file, VOICE_DIR / f"{key}.json", key, get_chapter(key))
    for kr_file in sorted(DTALE_KR_DIR.glob("KR_*.json")):
        key = kr_file.stem[3:]
        _load_story_file(kr_file, DTALE_V_DIR / f"{key}.json", key, get_dtale_chapter(key))
    print(f"[봇] 스토리 {len(search_data)}개 대사 로드 완료")

def _load_story_file(kr_file: Path, voice_file: Path, key: str, chapter: str):
    try:
        with open(kr_file, encoding="utf-8") as f:
            kr_list = json.load(f)["dataList"]
    except Exception as e:
        print(f"[경고] {kr_file.name} 로드 실패: {e}")
        return
    voice_map: Dict = {}
    if voice_file.exists():
        try:
            with open(voice_file, encoding="utf-8") as f:
                voice_list = json.load(f)["dataList"]
            voice_map = {item["id"]: item for item in voice_list if "id" in item}
        except Exception as e:
            print(f"[경고] {voice_file.name} 로드 실패: {e}")
    for item in kr_list:
        if "id" not in item or "content" not in item:
            continue
        vid = item["id"]
        voice_entry = voice_map.get(vid, {})
        search_data.append({
            "scene":   key,
            "chapter": chapter,
            "id":      vid,
            "model":   item.get("model", ""),
            "content": item["content"],
            "place":   item.get("place", ""),
            "voice":   voice_entry.get("voice", "")
        })


# ── Misc 데이터 로드 ─────────────────────────
def load_misc_data():
    misc_data.clear()
    for kr_file in sorted(MISC_DIR.glob("KR_*.json")):
        key = kr_file.stem[3:]
        category = get_misc_category(key)
        try:
            with open(kr_file, encoding="utf-8") as f:
                data = json.load(f)
        except Exception as e:
            print(f"[경고] {kr_file.name} 로드 실패: {e}")
            continue
        if "dataList" not in data:
            continue
        for item in data["dataList"]:
            if "id" not in item:
                continue
            for entry in _extract_misc_entries(item, category, key):
                misc_data.append(entry)
    print(f"[봇] Misc {len(misc_data)}개 항목 로드 완료")

def _extract_misc_entries(item: dict, category: str, scene: str) -> list:
    vid = item["id"]
    base = {"scene": scene, "category": category, "id": vid}

    if category == "스킬설명":
        lvs = item.get("levelList", [])
        if not lvs: return []
        last = lvs[-1]
        name = last.get("name", "")
        desc = last.get("desc", "")
        text = f"{name}: {desc}" if name and desc else name or desc
        if not text: return []
        return [{**base, "speaker": "", "content": text, "extra": name}]

    if category in ("패시브", "EGO"):
        name = item.get("name", "")
        desc = item.get("desc", "")
        text = f"{name}: {desc}" if name and desc else name or desc
        if not text: return []
        return [{**base, "speaker": "", "content": text, "extra": name}]

    if category == "선택지대사":
        dialog = item.get("dialog", "")
        if not dialog: return []
        return [{**base, "speaker": item.get("teller", ""), "content": dialog, "extra": ""}]

    if category in ("어나운서", "배틀대사"):
        text = item.get("dlg", "") or item.get("desc", "")
        if not text: return []
        return [{**base, "speaker": "", "content": text, "extra": ""}]

    # BGM가사, 단테노트, 기타
    text = str(item.get("content") or item.get("dlg") or item.get("dialog") or item.get("desc") or "")
    if not text: return []
    return [{**base, "speaker": "", "content": text, "extra": ""}]


# ── 검색 함수 ────────────────────────────────
def do_search(keyword: Optional[str], filter_val: Optional[str], speaker: Optional[str]) -> List[Dict]:
    results = []
    kw = keyword.lower() if keyword else None
    sp = speaker.lower() if speaker else None
    for entry in search_data:
        if filter_val:
            c = entry["chapter"]
            if filter_val == "main_all" and c not in MAIN_CHAPTERS: continue
            elif filter_val == "inter_all" and c not in INTER_CHAPTERS: continue
            elif filter_val == "기타" and c != "기타": continue
            elif filter_val not in ("main_all", "inter_all", "기타") and c != filter_val: continue
        if sp and sp not in entry["model"].lower(): continue
        if kw and kw not in entry["content"].lower(): continue
        results.append(entry)
    return results

def do_misc_search(keyword: Optional[str], category: Optional[str]) -> List[Dict]:
    results = []
    kw = keyword.lower() if keyword else None
    for entry in misc_data:
        if category and category != "all" and entry["category"] != category: continue
        if kw and kw not in entry["content"].lower(): continue
        results.append(entry)
    return results


# ── 페이지 이동 Modal ────────────────────────
class GotoPageModal(discord.ui.Modal, title="페이지 이동"):
    page_num = discord.ui.TextInput(
        label="이동할 페이지 번호",
        placeholder="숫자를 입력하게.",
        min_length=1,
        max_length=5,
    )

    def __init__(self, view: "SearchView"):
        super().__init__()
        self.search_view = view

    async def on_submit(self, interaction: discord.Interaction):
        try:
            target = int(self.page_num.value) - 1
            if target < 0 or target > self.search_view.max_page:
                await interaction.response.send_message(
                    f"1 ~ {self.search_view.max_page + 1} 사이의 숫자를 입력하게.", ephemeral=True
                )
                return
            self.search_view.page = target
            self.search_view._update_buttons()
            await interaction.response.edit_message(embed=self.search_view.make_embed(), view=self.search_view)
        except ValueError:
            await interaction.response.send_message("숫자만 입력하게.", ephemeral=True)


# ── 스토리 검색 뷰 ───────────────────────────
class SearchView(discord.ui.View):
    def __init__(self, results: List[Dict], keyword: Optional[str], chapter_label: str, speaker: Optional[str]):
        super().__init__(timeout=180)
        self.results       = results
        self.keyword       = keyword
        self.chapter_label = chapter_label
        self.speaker       = speaker
        self.page          = 0
        self.max_page      = (len(results) - 1) // RESULTS_PER_PAGE
        self._update_buttons()

    def _update_buttons(self):
        self.prev_btn.disabled = (self.page == 0)
        self.next_btn.disabled = (self.page == self.max_page)

    def make_embed(self) -> discord.Embed:
        start = self.page * RESULTS_PER_PAGE
        page_results = self.results[start:start + RESULTS_PER_PAGE]

        kw_str      = f"**키워드:** `{self.keyword}`　" if self.keyword else ""
        speaker_str = f"**화자:** `{self.speaker}`　"  if self.speaker else ""
        embed = discord.Embed(
            title="🔍 림버스 컴퍼니 대사 검색",
            description=(
                f"{kw_str}{speaker_str}"
                f"**장:** {self.chapter_label}　"
                f"**{len(self.results)}개 결과** "
                f"({self.page + 1} / {self.max_page + 1} 페이지)"
            ),
            color=0xE4444F
        )
        for r in page_results:
            model     = r["model"] if r["model"] else "내레이션"
            voice     = f"`{r['voice']}`" if r["voice"] else "❌ 없음"
            place_str = f"\n📍 _{r['place']}_" if r["place"] else ""
            embed.add_field(
                name=f"[{r['scene']}] {model}",
                value=f"{r['content']}{place_str}\n🔊 음성: {voice}",
                inline=False
            )
        embed.set_footer(text=random.choice(FOOTER_MESSAGES))
        return embed

    @discord.ui.button(label="페이지 이동", style=discord.ButtonStyle.primary)
    async def goto_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(GotoPageModal(self))

    @discord.ui.button(label="◀ 이전", style=discord.ButtonStyle.secondary)
    async def prev_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.page -= 1
        self._update_buttons()
        await interaction.response.edit_message(embed=self.make_embed(), view=self)

    @discord.ui.button(label="다음 ▶", style=discord.ButtonStyle.secondary)
    async def next_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.page += 1
        self._update_buttons()
        await interaction.response.edit_message(embed=self.make_embed(), view=self)


# ── Misc 검색 뷰 ─────────────────────────────
class MiscSearchView(discord.ui.View):
    def __init__(self, results: List[Dict], keyword: Optional[str], category_label: str):
        super().__init__(timeout=180)
        self.results        = results
        self.keyword        = keyword
        self.category_label = category_label
        self.page           = 0
        self.max_page       = (len(results) - 1) // RESULTS_PER_PAGE
        self._update_buttons()

    def _update_buttons(self):
        self.prev_btn.disabled = (self.page == 0)
        self.next_btn.disabled = (self.page == self.max_page)

    def make_embed(self) -> discord.Embed:
        start = self.page * RESULTS_PER_PAGE
        page_results = self.results[start:start + RESULTS_PER_PAGE]

        kw_str = f"**키워드:** `{self.keyword}`　" if self.keyword else ""
        embed = discord.Embed(
            title="📖 림버스 컴퍼니 설명 검색",
            description=(
                f"{kw_str}"
                f"**카테고리:** {self.category_label}　"
                f"**{len(self.results)}개 결과** "
                f"({self.page + 1} / {self.max_page + 1} 페이지)"
            ),
            color=0x5865F2
        )
        for r in page_results:
            speaker_str = f" ({r['speaker']})" if r.get("speaker") else ""
            embed.add_field(
                name=f"[{r['scene']}] {r['category']}{speaker_str}",
                value=r["content"][:1000],
                inline=False
            )
        embed.set_footer(text=random.choice(FOOTER_MESSAGES))
        return embed

    @discord.ui.button(label="페이지 이동", style=discord.ButtonStyle.primary)
    async def goto_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(GotoPageModal(self))

    @discord.ui.button(label="◀ 이전", style=discord.ButtonStyle.secondary)
    async def prev_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.page -= 1
        self._update_buttons()
        await interaction.response.edit_message(embed=self.make_embed(), view=self)

    @discord.ui.button(label="다음 ▶", style=discord.ButtonStyle.secondary)
    async def next_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.page += 1
        self._update_buttons()
        await interaction.response.edit_message(embed=self.make_embed(), view=self)


# ── 봇 설정 ─────────────────────────────────
intents = discord.Intents.default()
bot = commands.Bot(command_prefix="!", intents=intents)


@bot.event
async def on_ready():
    load_all_data()
    load_misc_data()
    await bot.tree.sync()
    print(f"[봇] 로그인 완료: {bot.user} (ID: {bot.user.id})")
    print("[봇] 슬래시 커맨드 동기화 완료")


# ── /대사검색 ────────────────────────────────
@bot.tree.command(name="대사검색", description="림버스 컴퍼니 스토리 대사를 검색하게.")
@app_commands.describe(
    키워드="검색할 단어 또는 문장 (비워두면 전체)",
    화자="캐릭터 이름 (예: 홍루, 단테 / 비워두면 전체)",
    장="검색 범위 (비워두면 전체 검색)"
)
@app_commands.choices(장=[
    app_commands.Choice(name="전체",              value="all"),
    app_commands.Choice(name="메인스토리 전체",   value="main_all"),
    app_commands.Choice(name="1장",               value="1"),
    app_commands.Choice(name="2장",               value="2"),
    app_commands.Choice(name="3장",               value="3"),
    app_commands.Choice(name="4장",               value="4"),
    app_commands.Choice(name="5장",               value="5"),
    app_commands.Choice(name="6장",               value="6"),
    app_commands.Choice(name="7장",               value="7"),
    app_commands.Choice(name="8장",               value="8"),
    app_commands.Choice(name="9장",               value="9"),
    app_commands.Choice(name="인터발로 전체",     value="inter_all"),
    app_commands.Choice(name="3.5장 헬스 치킨",   value="3.5"),
    app_commands.Choice(name="4.5장 우.미.다",    value="4.5"),
    app_commands.Choice(name="5.5장",             value="5.5"),
    app_commands.Choice(name="6.5장",             value="6.5"),
    app_commands.Choice(name="7.5장",             value="7.5"),
    app_commands.Choice(name="8.5장",             value="8.5"),
    app_commands.Choice(name="9.5장",             value="9.5"),
    app_commands.Choice(name="기타 전체 (미니스토리/발푸밤 등)", value="기타"),
])
async def search_command(
    interaction: discord.Interaction,
    키워드: Optional[str] = None,
    화자: Optional[str] = None,
    장: Optional[app_commands.Choice[str]] = None,
):
    await interaction.response.defer()

    if not 키워드 and not 화자 and not 장:
        await interaction.followup.send("키워드, 화자, 장 중 하나 이상은 입력해야 하네.", ephemeral=True)
        return

    if 장 is None or 장.value == "all":
        filter_val, chapter_label = None, "전체"
    else:
        filter_val, chapter_label = 장.value, 장.name

    results = do_search(키워드, filter_val, 화자)

    if not results:
        parts = []
        if 키워드: parts.append(f"키워드: {키워드}")
        if 화자:   parts.append(f"화자: {화자}")
        parts.append(f"장: {chapter_label}")
        await interaction.followup.send(f"{' / '.join(parts)} — 해당하는 대사를 찾지 못했네.")
        return

    view  = SearchView(results, 키워드, chapter_label, 화자)
    await interaction.followup.send(embed=view.make_embed(), view=view)


# ── /기타 검색 ────────────────────────────────
@bot.tree.command(name="기타검색", description="인격/스킬/EGO 등 게임 내 설명을 검색하게.")
@app_commands.describe(
    키워드="검색할 단어 또는 문장 (비워두면 전체)",
    카테고리="검색 범위 (비워두면 전체)"
)
@app_commands.choices(카테고리=[
    app_commands.Choice(name="전체",        value="all"),
    app_commands.Choice(name="어나운서",    value="어나운서"),
    app_commands.Choice(name="선택지 대사", value="선택지 대사"),
    app_commands.Choice(name="스킬 설명",   value="스킬설명"),
    app_commands.Choice(name="패시브",      value="패시브"),
    app_commands.Choice(name="EGO",         value="EGO"),
    app_commands.Choice(name="배틀 대사",   value="배틀대사"),
    app_commands.Choice(name="BGM 가사",    value="BGM가사"),
    app_commands.Choice(name="단테 노트",   value="단테노트"),
    app_commands.Choice(name="기타",        value="기타"),
])
async def misc_search_command(
    interaction: discord.Interaction,
    키워드: Optional[str] = None,
    카테고리: Optional[app_commands.Choice[str]] = None,
):
    await interaction.response.defer()

    if not 키워드 and not 카테고리:
        await interaction.followup.send("키워드 또는 카테고리 중 하나는 입력해야 하네.", ephemeral=True)
        return

    cat_val   = 카테고리.value if 카테고리 else "all"
    cat_label = 카테고리.name  if 카테고리 else "전체"

    results = do_misc_search(키워드, cat_val)

    if not results:
        parts = []
        if 키워드: parts.append(f"키워드: {키워드}")
        parts.append(f"카테고리: {cat_label}")
        await interaction.followup.send(f"{' / '.join(parts)} — 해당하는 내용을 찾지 못했네.")
        return

    view = MiscSearchView(results, 키워드, cat_label)
    await interaction.followup.send(embed=view.make_embed(), view=view)


# ── 실행 ─────────────────────────────────────
if __name__ == "__main__":
    token = os.getenv("TOKEN")
    if not token:
        raise ValueError("[봇] .env 파일에 TOKEN이 없습니다!")
    bot.run(token)
