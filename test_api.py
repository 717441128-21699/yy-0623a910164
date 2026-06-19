import base64
import json
import requests
from datetime import date, timedelta
import os

BASE_URL = "http://localhost:8000"


def create_test_image(width=640, height=480, color=(200, 200, 200)):
    try:
        from PIL import Image
        import io
        img = Image.new('RGB', (width, height), color)
        buf = io.BytesIO()
        img.save(buf, format='JPEG')
        return base64.b64encode(buf.getvalue()).decode('utf-8')
    except ImportError:
        import array
        import struct
        import zlib

        raw_data = b''
        for y in range(height):
            raw_data += b'\xff'
            for x in range(width):
                raw_data += bytes(color)

        import base64 as b64
        png_header = b'\x89PNG\r\n\x1a\n'

        def make_chunk(chunk_type, data):
            chunk_len = struct.pack('>I', len(data))
            chunk_crc = struct.pack('>I', zlib.crc32(chunk_type + data) & 0xffffffff)
            return chunk_len + chunk_type + data + chunk_crc

        ihdr_data = struct.pack('>IIBBBBB', width, height, 8, 2, 0, 0, 0)
        ihdr = make_chunk(b'IHDR', ihdr_data)

        idat_data = zlib.compress(raw_data)
        idat = make_chunk(b'IDAT', idat_data)

        iend = make_chunk(b'IEND', b'')

        png_data = png_header + ihdr + idat + iend
        return b64.b64encode(png_data).decode('utf-8')


def test_root():
    print("=" * 50)
    print("测试1: 获取系统信息")
    print("=" * 50)
    try:
        response = requests.get(f"{BASE_URL}/")
        data = response.json()
        print(f"服务名称: {data.get('name')}")
        print(f"版本: {data.get('version')}")
        print(f"标准角度数: {len(data.get('standard_angles', []))}")
        print("✓ 测试通过\n")
        return True
    except Exception as e:
        print(f"✗ 测试失败: {e}\n")
        return False


def test_standard_angles():
    print("=" * 50)
    print("测试2: 获取标准角度列表")
    print("=" * 50)
    try:
        response = requests.get(f"{BASE_URL}/api/standard-angles")
        data = response.json()
        angles = data.get('angles', [])
        for i, angle in enumerate(angles, 1):
            print(f"  {i}. {angle}")
        print(f"✓ 共 {len(angles)} 个标准角度\n")
        return True
    except Exception as e:
        print(f"✗ 测试失败: {e}\n")
        return False


def test_submit_photos():
    print("=" * 50)
    print("测试3: 提交初诊照片")
    print("=" * 50)
    try:
        test_img = create_test_image()

        angles = ["正面面相", "侧面面相", "口内正面像", "口内左侧面像"]
        photos = [{"angle": angle, "image_base64": test_img} for angle in angles]

        payload = {
            "patient_no": "P2024001",
            "patient_name": "张三",
            "visit_date": "2024-01-15",
            "is_initial": True,
            "photos": photos
        }

        response = requests.post(
            f"{BASE_URL}/api/photos/submit",
            json=payload
        )
        data = response.json()

        print(f"提交状态: {'成功' if data.get('success') else '失败'}")
        print(f"患者编号: {data.get('patient_no')}")
        print(f"复诊日期: {data.get('visit_date')}")
        print(f"完整度: 已提交 {data['completeness']['submitted_count']}/{data['completeness']['total_required']} 个角度")
        print(f"缺失角度: {', '.join(data['completeness']['missing_angles'])}")
        print(f"质量合格: {data['completeness']['quality_passed_count']} 张")
        print(f"质量待改善: {data['completeness']['quality_failed_count']} 张")
        print("✓ 提交照片测试通过\n")
        return True
    except Exception as e:
        print(f"✗ 测试失败: {e}\n")
        return False


def test_submit_second_visit():
    print("=" * 50)
    print("测试4: 提交复诊照片")
    print("=" * 50)
    try:
        test_img = create_test_image(color=(180, 180, 180))

        angles = ["正面面相", "侧面面相", "45°侧面面相", "口内正面像", "口内左侧面像", "口内右侧面像"]
        photos = [{"angle": angle, "image_base64": test_img} for angle in angles]

        payload = {
            "patient_no": "P2024001",
            "patient_name": "张三",
            "visit_date": "2024-03-15",
            "is_initial": False,
            "photos": photos
        }

        response = requests.post(
            f"{BASE_URL}/api/photos/submit",
            json=payload
        )
        data = response.json()

        print(f"提交状态: {'成功' if data.get('success') else '失败'}")
        print(f"患者编号: {data.get('patient_no')}")
        print(f"复诊日期: {data.get('visit_date')}")
        print(f"完整度: 已提交 {data['completeness']['submitted_count']}/{data['completeness']['total_required']} 个角度")
        print(f"缺失角度: {', '.join(data['completeness']['missing_angles'])}")
        print("✓ 复诊照片提交测试通过\n")
        return True
    except Exception as e:
        print(f"✗ 测试失败: {e}\n")
        return False


def test_compare_initial():
    print("=" * 50)
    print("测试5: 初诊 vs 本次 对比")
    print("=" * 50)
    try:
        payload = {
            "patient_no": "P2024001",
            "compare_mode": "initial_vs_current",
            "current_visit_date": "2024-03-15"
        }

        response = requests.post(
            f"{BASE_URL}/api/compare/generate",
            json=payload
        )
        data = response.json()

        print(f"状态: {'成功' if data.get('success') else '失败'}")
        print(f"对比模式: {data.get('compare_mode')}")
        print(f"对比日期: {data.get('before_visit_date')} → {data.get('after_visit_date')}")
        print(f"对比角度数: {data.get('angles_compared')}")
        print(f"AI提示: {data.get('ai_hint', '')[:100]}...")
        print("✓ 初诊对比测试通过\n")
        return True
    except Exception as e:
        print(f"✗ 测试失败: {e}\n")
        return False


def test_compare_last():
    print("=" * 50)
    print("测试6: 上次 vs 本次 对比")
    print("=" * 50)
    try:
        payload = {
            "patient_no": "P2024001",
            "compare_mode": "last_vs_current",
            "current_visit_date": "2024-03-15"
        }

        response = requests.post(
            f"{BASE_URL}/api/compare/generate",
            json=payload
        )
        data = response.json()

        print(f"状态: {'成功' if data.get('success') else '失败'}")
        print(f"对比模式: {data.get('compare_mode')}")
        print(f"对比日期: {data.get('before_visit_date')} → {data.get('after_visit_date')}")
        print(f"对比角度数: {data.get('angles_compared')}")
        print(f"AI提示: {data.get('ai_hint', '')[:100]}...")
        print("✓ 上次对比测试通过\n")
        return True
    except Exception as e:
        print(f"✗ 测试失败: {e}\n")
        return False


def test_admin_logs():
    print("=" * 50)
    print("测试7: 获取接口调用记录")
    print("=" * 50)
    try:
        response = requests.get(f"{BASE_URL}/api/admin/logs?limit=5")
        data = response.json()

        print(f"状态: {'成功' if data.get('success') else '失败'}")
        print(f"总记录数: {data.get('total')}")
        print(f"返回记录数: {len(data.get('logs', []))}")
        if data.get('logs'):
            latest = data['logs'][0]
            print(f"  最新调用: {latest['endpoint']} - 状态 {latest['status_code']}")
        print("✓ 调用记录测试通过\n")
        return True
    except Exception as e:
        print(f"✗ 测试失败: {e}\n")
        return False


def test_admin_abnormal_photos():
    print("=" * 50)
    print("测试8: 获取异常照片清单")
    print("=" * 50)
    try:
        response = requests.get(f"{BASE_URL}/api/admin/abnormal-photos?limit=5")
        data = response.json()

        print(f"状态: {'成功' if data.get('success') else '失败'}")
        print(f"异常照片总数: {data.get('total')}")
        print(f"返回数量: {len(data.get('photos', []))}")
        print("✓ 异常照片测试通过\n")
        return True
    except Exception as e:
        print(f"✗ 测试失败: {e}\n")
        return False


def test_admin_stats():
    print("=" * 50)
    print("测试9: 获取统计数据")
    print("=" * 50)
    try:
        response = requests.get(f"{BASE_URL}/api/admin/stats")
        data = response.json()

        print(f"状态: {'成功' if data.get('success') else '失败'}")
        print(f"患者总数: {data.get('total_patients')}")
        print(f"照片总数: {data.get('total_photos')}")
        print(f"对比次数: {data.get('total_compares')}")
        print(f"API调用次数: {data.get('total_api_calls')}")
        print(f"异常照片数: {data.get('abnormal_photo_count')}")
        print("✓ 统计数据测试通过\n")
        return True
    except Exception as e:
        print(f"✗ 测试失败: {e}\n")
        return False


def main():
    print("\n")
    print("╔" + "=" * 48 + "╗")
    print("║     正畸复诊拍照对比服务 - API测试套件     ║")
    print("╚" + "=" * 48 + "╝")
    print()

    tests = [
        test_root,
        test_standard_angles,
        test_submit_photos,
        test_submit_second_visit,
        test_compare_initial,
        test_compare_last,
        test_admin_logs,
        test_admin_abnormal_photos,
        test_admin_stats,
    ]

    results = []
    for test in tests:
        try:
            result = test()
            results.append(result)
        except Exception as e:
            print(f"✗ 测试异常: {e}\n")
            results.append(False)

    passed = sum(results)
    total = len(results)

    print("=" * 50)
    print(f"测试结果: {passed}/{total} 通过")
    print("=" * 50)

    if passed == total:
        print("🎉 所有测试通过！服务运行正常。")
    else:
        print(f"⚠️  有 {total - passed} 个测试失败，请检查服务状态。")

    print()


if __name__ == "__main__":
    main()
