"""
pii-masker テストスイート

テスト実行:
  pytest tests/ -v
"""

import pytest
from pathlib import Path
from pii_masker import Masker


# ━━ フィクスチャ ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

@pytest.fixture
def masker():
    m = Masker()
    return m


@pytest.fixture
def fresh_masker():
    """テストごとにリセットされたMasker"""
    m = Masker()
    m.reset()
    return m


# ━━ 日付 ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

class TestDateMasking:

    def test_japanese_date(self, masker):
        assert "【日付" in masker.mask("2025年4月1日")

    def test_wareki(self, masker):
        assert "【日付" in masker.mask("令和7年4月1日")

    def test_wareki_abbrev(self, masker):
        assert "【日付" in masker.mask("R7.4.1")

    def test_slash_format(self, masker):
        assert "【日付" in masker.mask("2025/04/01")

    def test_hyphen_format(self, masker):
        assert "【日付" in masker.mask("2025-04-01")

    def test_dot_format(self, masker):
        assert "【日付" in masker.mask("2025.04.01")

    def test_8digit(self, masker):
        assert "【日付" in masker.mask("20250401")

    def test_month_day_only(self, masker):
        assert "【日付" in masker.mask("4月1日に開催")

    def test_english_date(self, masker):
        assert "【日付" in masker.mask("April 1, 2025")

    def test_fullwidth(self, masker):
        assert "【日付" in masker.mask("２０２５年４月１日")

    def test_kanji_digits(self, masker):
        assert "【日付" in masker.mask("二〇二五年四月一日")

    def test_no_false_positive_phone(self, masker):
        result = masker.mask("03-1234-5678")
        assert "【日付" not in result

    def test_no_false_positive_amount(self, masker):
        result = masker.mask("3,000万円")
        assert "【日付" not in result


# ━━ 金額・数値 ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

class TestAmountMasking:

    def test_amount_with_unit(self, masker):
        result = masker.mask("3,000万円")
        assert "【金額" in result
        assert "万円" in result   # 単位は残す

    def test_amount_oku(self, masker):
        result = masker.mask("150億円")
        assert "【金額" in result
        assert "億円" in result

    def test_numeric_kg(self, masker):
        result = masker.mask("重量2.5kg")
        assert "【数値" in result
        assert "kg" in result

    def test_numeric_celsius(self, masker):
        result = masker.mask("温度85℃")
        assert "【数値" in result
        assert "℃" in result

    def test_numeric_days(self, masker):
        result = masker.mask("納期45日")
        assert "【数値" in result
        assert "日" in result


# ━━ 年齢 ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

class TestAgeMasking:

    @pytest.mark.parametrize("age,decade", [
        ("42歳", "40代"),
        ("38歳", "30代"),
        ("25歳", "20代"),
        ("65歳", "60代"),
    ])
    def test_age_to_decade(self, masker, age, decade):
        assert decade in masker.mask(age)

    def test_age_irreversible(self, masker, tmp_path):
        """年齢変換は非可逆"""
        masked = masker.mask("42歳")
        map_path = tmp_path / "mapping.tsv"
        masker.save_mapping(map_path)
        restored = masker.restore(masked, map_path)
        assert "42歳" not in restored   # 復元不可


# ━━ 住所 ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

class TestAddressMasking:

    def test_full_address(self, masker):
        result = masker.mask("東京都千代田区丸の内1-1-1")
        assert "東京都" in result       # 都道府県は残す
        assert "千代田区" not in result  # 市区町村以降はマスク

    def test_postal_code(self, masker):
        result = masker.mask("〒160-0023 新宿区西新宿2-8-1")
        assert "〒" in result
        assert "【住所" in result

    def test_branch_office(self, masker):
        result = masker.mask("東京支社との会議")
        assert "【住所" in result
        assert "支社" in result   # サフィックスは残す

    def test_prefecture_standalone_not_masked(self, masker):
        """都道府県単独（後続なし）はマスクしない"""
        result = masker.mask("大阪府の規制によると")
        assert "大阪府" in result


# ━━ 連絡先 ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

class TestContactMasking:

    def test_phone_domestic(self, masker):
        assert "【電話" in masker.mask("03-1234-5678")

    def test_phone_mobile(self, masker):
        assert "【電話" in masker.mask("090-9876-5432")

    def test_email(self, masker):
        assert "【メール" in masker.mask("tanaka@example.co.jp")

    def test_sns_at(self, masker):
        assert "【SNS" in masker.mask("@tanaka_taro")

    def test_sns_github(self, masker):
        assert "【SNS" in masker.mask("github.com/tanaka")


# ━━ 番号類 ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

class TestNumberMasking:

    def test_model_number(self, masker):
        assert "【型番" in masker.mask("型番：ABC-12345-XZ")

    def test_serial_number(self, masker):
        assert "【シリアル" in masker.mask("シリアル：SN20251234")

    def test_patent_jp(self, masker):
        result = masker.mask("特許第6123456号")
        assert "【特許" in result
        assert "特許" in result   # 前の「特許」は残る
        assert "号" in result

    def test_patent_us(self, masker):
        assert "【特許" in masker.mask("US Patent 9,123,456")


# ━━ 人物・組織 ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

class TestNERMasking:

    def test_person_with_title(self, masker):
        result = masker.mask("田中太郎部長")
        assert "【人物" in result
        assert "部長" in result   # 役職は残す

    def test_person_with_honorific(self, masker):
        result = masker.mask("鈴木花子さん")
        assert "【人物" in result
        assert "さん" in result   # 敬称は残す

    def test_org_kabushiki(self, masker):
        assert "【組織" in masker.mask("ABC株式会社")

    def test_org_prefix(self, masker):
        assert "【組織" in masker.mask("株式会社XYZテクノロジー")


# ━━ 一意性 ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

class TestUniqueness:

    def test_same_input_same_token(self, fresh_masker):
        """同じ文字列は常に同じトークン"""
        r1 = fresh_masker.mask("03-1234-5678")
        r2 = fresh_masker.mask("03-1234-5678")
        assert r1 == r2

    def test_different_input_different_token(self, fresh_masker):
        """異なる文字列は異なるトークン"""
        r1 = fresh_masker.mask("03-1234-5678")
        r2 = fresh_masker.mask("090-9876-5432")
        # トークンIDが異なる (A vs B)
        assert r1 != r2

    def test_token_order(self, fresh_masker):
        """登場順にA,B,C...と採番される"""
        text = "03-1111-0001と03-2222-0002と03-3333-0003"
        result = fresh_masker.mask(text)
        assert "【電話A】" in result
        assert "【電話B】" in result
        assert "【電話C】" in result


# ━━ 可逆性（復元） ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

class TestRestore:

    def test_restore_basic(self, fresh_masker, tmp_path):
        original = "田中太郎部長、03-1234-5678、tanaka@example.co.jp"
        masked = fresh_masker.mask(original)
        map_path = tmp_path / "mapping.tsv"
        fresh_masker.save_mapping(map_path)
        restored = fresh_masker.restore(masked, map_path)
        assert restored == original

    def test_restore_date(self, fresh_masker, tmp_path):
        original = "2025年4月1日の会議"
        masked = fresh_masker.mask(original)
        map_path = tmp_path / "mapping.tsv"
        fresh_masker.save_mapping(map_path)
        restored = fresh_masker.restore(masked, map_path)
        assert restored == original

    def test_restore_address(self, fresh_masker, tmp_path):
        original = "東京都千代田区丸の内1-1-1"
        masked = fresh_masker.mask(original)
        map_path = tmp_path / "mapping.tsv"
        fresh_masker.save_mapping(map_path)
        restored = fresh_masker.restore(masked, map_path)
        assert restored == original

    def test_restore_postal(self, fresh_masker, tmp_path):
        original = "〒231-0001 神奈川県横浜市中区新港1-1"
        masked = fresh_masker.mask(original)
        map_path = tmp_path / "mapping.tsv"
        fresh_masker.save_mapping(map_path)
        restored = fresh_masker.restore(masked, map_path)
        assert restored == original


# ━━ セッション間一貫性 ━━━━━━━━━━━━━━━━━━━━━━━━━━━

class TestCrossSessionConsistency:

    def test_same_label_across_sessions(self, tmp_path):
        """マッピングを引き継ぐと異なるセッションでも同じラベルになる"""
        map_path = tmp_path / "shared_mapping.tsv"

        # セッション1: 田中が先に登場 → 人物A
        m1 = Masker()
        r1 = m1.mask("田中太郎部長と鈴木花子さん")
        m1.save_mapping(map_path)
        assert "【人物A】" in r1  # 田中 → A

        # セッション2: 鈴木が先に登場するが、事前ロードで田中=A・鈴木=B を引き継ぐ
        m2 = Masker()
        m2.load_mapping(map_path)
        r2 = m2.mask("鈴木花子さんと田中太郎部長")
        assert "【人物A】" in r2  # 田中 → 依然A（順序に関わらず）
        assert "【人物B】" in r2  # 鈴木 → 依然B

    def test_backup_created_on_save(self, tmp_path):
        """2回保存すると .bak が作られる"""
        map_path = tmp_path / "mapping.tsv"

        m1 = Masker()
        m1.mask("03-1234-5678")
        m1.save_mapping(map_path)
        assert not map_path.with_name(map_path.name + ".bak").exists()

        m2 = Masker()
        m2.mask("090-9876-5432")
        m2.save_mapping(map_path)
        assert map_path.with_name(map_path.name + ".bak").exists()  # バックアップ生成

    def test_tsv_format(self, tmp_path):
        """保存されたTSVが4列（カテゴリ/元テキスト/MD5/ラベル）になっている"""
        map_path = tmp_path / "mapping.tsv"
        m = Masker()
        m.mask("03-1234-5678")
        m.save_mapping(map_path)

        lines = [l for l in map_path.read_text(encoding="utf-8").splitlines()
                 if l and not l.startswith("#")]
        assert len(lines) >= 1
        assert all(len(l.split("\t")) == 4 for l in lines)


# ━━ ファイルハンドラー ━━━━━━━━━━━━━━━━━━━━━━━━━━━

class TestFileHandlers:

    def test_txt_handler(self, fresh_masker, tmp_path):
        from pii_masker.formats.handler_txt import process_txt
        src = tmp_path / "test.txt"
        src.write_text("田中太郎部長、03-1234-5678、2025年4月1日", encoding="utf-8")
        output, orig, masked = process_txt(src, fresh_masker)
        assert "【電話" in masked
        assert "【日付" in masked

    def test_html_handler(self, fresh_masker, tmp_path):
        from pii_masker.formats.handler_html import process_html
        src = tmp_path / "test.html"
        src.write_text(
            "<html><body><p>田中太郎部長、03-1234-5678</p></body></html>",
            encoding="utf-8"
        )
        output, orig, masked = process_html(src, fresh_masker)
        assert "<p>" in output        # タグは保持
        assert "【電話" in masked

    def test_svg_handler(self, fresh_masker, tmp_path):
        from pii_masker.formats.handler_svg import process_svg
        src = tmp_path / "test.svg"
        src.write_text(
            '<?xml version="1.0"?>'
            '<svg xmlns="http://www.w3.org/2000/svg">'
            '<text>田中太郎部長、03-1234-5678</text>'
            '</svg>',
            encoding="utf-8"
        )
        output, orig, masked = process_svg(src, fresh_masker)
        assert "<text>" in output or "text" in output
        assert "【電話" in masked


# ━━ CLI ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

class TestCLI:

    def test_mask_command(self, tmp_path):
        import argparse
        from pii_masker.cli import cmd_mask

        src = tmp_path / "input.txt"
        src.write_text("田中太郎部長、03-1234-5678、2025年4月1日", encoding="utf-8")

        args = argparse.Namespace(
            file=str(src),
            output=str(tmp_path / "output.txt"),
            mapping=str(tmp_path / "mapping.tsv"),
        )
        ret = cmd_mask(args)
        assert ret == 0
        assert (tmp_path / "output.txt").exists()
        assert (tmp_path / "mapping.tsv").exists()

    def test_unmask_command(self, tmp_path):
        import argparse
        from pii_masker.cli import cmd_mask, cmd_unmask

        src = tmp_path / "input.txt"
        original = "田中太郎部長、03-1234-5678、2025年4月1日"
        src.write_text(original, encoding="utf-8")

        masked_path = tmp_path / "input_masked.txt"
        map_path = tmp_path / "input_mapping.tsv"

        # まずマスク
        cmd_mask(argparse.Namespace(
            file=str(src),
            output=str(masked_path),
            mapping=str(map_path),
        ))

        # 復元
        restored_path = tmp_path / "restored.txt"
        ret = cmd_unmask(argparse.Namespace(
            file=str(masked_path),
            output=str(restored_path),
            mapping=str(map_path),
        ))
        assert ret == 0
        restored = restored_path.read_text(encoding="utf-8")
        assert restored == original

    def test_unmask_file_not_found(self, tmp_path):
        import argparse
        from pii_masker.cli import cmd_unmask

        args = argparse.Namespace(
            file=str(tmp_path / "nonexistent.txt"),
            output=None,
            mapping=None,
        )
        ret = cmd_unmask(args)
        assert ret == 1

    def test_mask_unsupported_format(self, tmp_path):
        import argparse
        from pii_masker.cli import cmd_mask

        src = tmp_path / "file.csv"
        src.write_text("name,phone\n田中太郎,03-1234-5678")

        args = argparse.Namespace(
            file=str(src),
            output=None,
            mapping=None,
        )
        ret = cmd_mask(args)
        assert ret == 1
