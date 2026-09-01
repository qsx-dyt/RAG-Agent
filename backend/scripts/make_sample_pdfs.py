from pathlib import Path
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont

SAMPLE_DIR = Path(__file__).resolve().parents[2] / "sample_data"
FONT_CANDIDATES = [
    r"C:\Windows\Fonts\msyh.ttc",
    "/usr/share/fonts/truetype/wqy/wqy-microhei.ttc",
]


def _register_font():
    for path in FONT_CANDIDATES:
        p = Path(path)
        if p.exists():
            pdfmetrics.registerFont(TTFont("CN", str(p)))
            return "CN"
    raise RuntimeError("未找到支持中文的 TTF 字体")


def _make_pdf(path: Path, title: str, lines: list[str]) -> None:
    font = _register_font()
    c = canvas.Canvas(str(path), pagesize=A4)
    c.setFont(font, 14)
    c.drawString(72, 800, title)
    c.setFont(font, 11)
    y = 770
    for line in lines:
        c.drawString(72, y, line)
        y -= 18
        if y < 60:
            c.showPage()
            c.setFont(font, 11)
            y = 800
    c.save()


def main() -> None:
    SAMPLE_DIR.mkdir(parents=True, exist_ok=True)
    _make_pdf(SAMPLE_DIR / "差旅管理规定.pdf", "差旅管理规定",
              ["1. 出差前需在系统提交出差申请并获得审批。",
               "2. 住宿标准:一线城市每晚不超过 500 元,其他城市不超过 350 元。",
               "3. 市内交通按实报销,需保留票据。",
               "4. 出差补贴:每人每天 100 元。"])
    _make_pdf(SAMPLE_DIR / "办公用品领用指南.pdf", "办公用品领用指南",
              ["1. 领用办公用品需填写领用单并经过部门负责人审批。",
               "2. 常用耗材(笔、纸)每月领用上限为 2 次。",
               "3. 单价超过 200 元的物品需行政部备案。",
               "4. 离职时需归还登记在个人名下的设备。"])


if __name__ == "__main__":
    main()
