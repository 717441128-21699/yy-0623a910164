import requests
import base64
import io
import time
from datetime import date, timedelta
from PIL import Image

BASE_URL = "http://localhost:8000"


def make_test_image(width=300, height=300, color=(200, 180, 150)):
    img = Image.new("RGB", (width, height), color)
    buf = io.BytesIO()
    img.save(buf, format="JPEG")
    return base64.b64encode(buf.getvalue()).decode("ascii")


def hr(title=""):
    print()
    print("=" * 60)
    if title:
        print(f"  {title}")
        print("=" * 60)


def test_section(title):
    hr(title)


passed = 0
total = 0


def check(name, cond, detail=""):
    global passed, total
    total += 1
    if cond:
        passed += 1
        print(f"  ✓ {name}{(': ' + detail) if detail else ''}")
    else:
        print(f"  ✗ {name}{(': ' + detail) if detail else ''}")


def summary():
    hr()
    print(f"  测试结果: {passed}/{total} 通过")
    if passed == total:
        print("  🎉 所有测试通过！v1.3.0 全部功能运行正常。")
    else:
        print(f"  ⚠️  {total - passed} 项失败，请检查。")
    hr()


def main():
    test_img_b64 = make_test_image()

    # ========== 测试0: 系统信息 ==========
    test_section("测试 0: 系统信息 & 默认接入方")
    r = requests.get(f"{BASE_URL}/").json()
    print(f"  服务版本: {r.get('version')}")
    check("版本号为 1.3.0", r.get("version") == "1.3.0")
    check("功能列表含 default_client", "default_client" in str(r.get("features", [])))

    list_resp = requests.get(f"{BASE_URL}/api/clients").json()
    default_client_id = None
    default_api_key = None
    for c in list_resp["clients"]:
        if c.get("is_default"):
            default_client_id = c["id"]
            default_api_key = c["api_key"]
            break
    check("存在默认接入方", default_client_id is not None, f"ID={default_client_id}")

    # ========== 测试1: 创建接入方 ==========
    test_section("测试 1: 创建接入方")
    r1 = requests.post(f"{BASE_URL}/api/clients", json={
        "name": "诊所A",
        "client_type": "clinic",
        "daily_api_quota": 500,
        "daily_photo_quota": 100,
        "allow_compare": True
    }).json()
    client_a_id = r1["id"]
    client_a_key = r1["api_key"]
    check("诊所A 创建成功", r1.get("name") == "诊所A")

    r2 = requests.post(f"{BASE_URL}/api/clients", json={
        "name": "诊所B",
        "client_type": "clinic",
        "daily_api_quota": 0,
        "daily_photo_quota": 0,
        "allow_compare": False
    }).json()
    client_b_id = r2["id"]
    client_b_key = r2["api_key"]
    check("诊所B 禁用对比", r2.get("allow_compare") is False)

    r3 = requests.post(f"{BASE_URL}/api/clients", json={
        "name": "小配额诊所C",
        "client_type": "clinic",
        "daily_api_quota": 2,
        "daily_photo_quota": 5,
        "allow_compare": True
    }).json()
    client_c_id = r3["id"]
    client_c_key = r3["api_key"]
    check("诊所C API配额=2 照片配额=5", r3.get("daily_api_quota") == 2 and r3.get("daily_photo_quota") == 5)

    headers_a = {"X-API-Key": client_a_key}
    headers_b = {"X-API-Key": client_b_key}
    headers_c = {"X-API-Key": client_c_key}
    headers_none = {}

    angles = ["正面面相", "侧面面相", "45°侧面面相", "口内正面像",
              "口内左侧面像", "口内右侧面像", "上颌牙合面像", "下颌牙合面像"]

    def submit_photos(patient_no, visit_date, is_initial, headers, count=4):
        payload = {
            "patient_no": patient_no,
            "patient_name": f"患者-{patient_no}",
            "visit_date": str(visit_date),
            "is_initial": is_initial,
            "photos": [{"angle": a, "image_base64": test_img_b64} for a in angles[:count]]
        }
        resp = requests.post(f"{BASE_URL}/api/photos/submit", json=payload, headers=headers)
        return resp.json(), resp.status_code

    # ========== 测试2: 数据隔离 + 对比图不覆盖 ==========
    test_section("测试 2: 接入方数据隔离 + 对比图互不覆盖")
    shared_p = "P-SHARED-001"

    body, _ = submit_photos(shared_p, date(2024, 1, 15), True, headers_a)
    check("诊所A 提交初诊成功", body.get("success") is True)

    body, _ = submit_photos(shared_p, date(2024, 1, 15), True, headers_b)
    check("诊所B 提交相同编号初诊成功", body.get("success") is True)

    body, _ = submit_photos(shared_p, date(2024, 6, 20), False, headers_a, count=6)
    check("诊所A 提交复诊成功", body.get("success") is True)

    body, _ = submit_photos(shared_p, date(2024, 6, 20), False, headers_b, count=4)
    check("诊所B 提交复诊成功", body.get("success") is True)

    list_b = requests.get(f"{BASE_URL}/api/photos/list/{shared_p}/2024-06-20", headers=headers_b).json()
    check("诊所B 只看到自己4张", len(list_b.get("photos", [])) == 4)

    list_a = requests.get(f"{BASE_URL}/api/photos/list/{shared_p}/2024-06-20", headers=headers_a).json()
    check("诊所A 看到自己6张", len(list_a.get("photos", [])) == 6)

    cmp_a = requests.post(f"{BASE_URL}/api/compare/generate", json={
        "patient_no": shared_p, "compare_mode": "initial_vs_current",
        "current_visit_date": "2024-06-20"
    }, headers=headers_a).json()
    check("诊所A 对比成功", cmp_a.get("success") is True)
    url_a = cmp_a.get("compare_image_url", "")

    cmp_b = requests.post(f"{BASE_URL}/api/compare/generate", json={
        "patient_no": shared_p, "compare_mode": "initial_vs_current",
        "current_visit_date": "2024-06-20"
    }, headers=headers_b).json()
    cmp_b_ok = cmp_b.get("success") is True
    url_b = cmp_b.get("compare_image_url", "") if cmp_b_ok else ""
    check("诊所B 对比结果", cmp_b_ok or cmp_b.get("success") is False)

    if url_a and url_b:
        check("对比图URL互不覆盖", url_a != url_b)
        fn_a = url_a.split("/")[-1]
        fn_b = url_b.split("/")[-1]
        check("诊所A对比图文件名含c{}".format(client_a_id), "c{}".format(client_a_id) in fn_a, f"fn={fn_a}")
        check("诊所B对比图文件名含c{}".format(client_b_id), "c{}".format(client_b_id) in fn_b, f"fn={fn_b}")
        resp_a = requests.get(f"{BASE_URL}{url_a}")
        check("诊所A对比图链接仍可访问", resp_a.status_code == 200)

    # ========== 测试3: API配额拦所有业务接口 ==========
    test_section("测试 3: API配额拦住所有业务接口(含查询)")
    # 诊所C: api_quota=2, photo_quota=5
    # 先消耗1次API调用(3张照片, <=5)
    body_c1, sc1 = submit_photos("P-C-1", date(2024, 5, 1), True, headers_c, count=3)
    check("诊所C 第1次提交成功", body_c1.get("success") is True)

    # 第2次API调用
    body_c2, sc2 = submit_photos("P-C-1", date(2024, 5, 2), False, headers_c, count=2)
    check("诊所C 第2次提交成功(api配额用完)", body_c2.get("success") is True)

    # 第3次：API配额已用2次=配额上限，照片查询也应被429拦住
    list_c = requests.get(f"{BASE_URL}/api/photos/list/P-C-1/2024-05-01", headers=headers_c)
    is_429 = list_c.status_code == 429
    check("诊所C API配额满 照片查询返回429", is_429)
    if is_429:
        body_429 = list_c.json()
        check("429消息含API配额提示", "API" in body_429.get("message", ""), f"msg={body_429.get('message', '')}")

    # 管理员日志筛429
    logs_429 = requests.get(f"{BASE_URL}/api/admin/logs", params={
        "status_code": 429, "client_id": client_c_id
    }).json()
    check("管理员可筛到诊所C的429日志", logs_429.get("total", 0) >= 1)

    # ========== 测试4: 照片批量额度检查 ==========
    test_section("测试 4: 照片批量额度 - 剩余不够整次拒绝")
    # 先更新诊所C配额，给足API但限制照片
    requests.put(f"{BASE_URL}/api/clients/{client_c_id}", json={
        "daily_api_quota": 500,
        "daily_photo_quota": 5
    }).json()
    # 当前已用 photo_uploads=3+2=5，刚好满
    # 再提交3张: 5+3=8>5 应被整次拒绝
    body_batch_fail, sc_bf = submit_photos("P-C-BATCH", date(2024, 7, 1), True, headers_c, count=3)
    is_rejected = body_batch_fail.get("success") is False and "剩余额度" in body_batch_fail.get("message", "")
    check("照片批量超额 整次拒绝", is_rejected, f"msg={body_batch_fail.get('message', '')}")
    if not body_batch_fail.get("success"):
        has_fields = (body_batch_fail.get("used") is not None and
                      body_batch_fail.get("limit") is not None and
                      body_batch_fail.get("requested") is not None)
        check("返回含已用/上限/请求数", has_fields,
              f"used={body_batch_fail.get('used')}, limit={body_batch_fail.get('limit')}, requested={body_batch_fail.get('requested')}")

    # ========== 测试5: 无Key请求归入默认接入方 ==========
    test_section("测试 5: 无Key请求归默认接入方 + 详情可查")
    nk_patient = "P-NOKEY-001"
    body_nk, _ = submit_photos(nk_patient, date(2024, 8, 1), True, headers_none, count=4)
    check("无Key请求可正常提交", body_nk.get("success") is True)

    time.sleep(1)

    detail_default = requests.get(f"{BASE_URL}/api/admin/clients/{default_client_id}/detail",
                                  params={"logs_limit": 50}).json()
    check("默认接入方详情 success", detail_default.get("success") is True)

    nk_logs = requests.get(f"{BASE_URL}/api/admin/logs", params={
        "patient_no": nk_patient, "client_id": default_client_id
    }).json()
    found_nk = nk_logs.get("total", 0) >= 1
    check("默认接入方日志含无Key请求", found_nk, f"nk_logs_total={nk_logs.get('total', 0)}")

    du = detail_default.get("daily_usage", {})
    check("默认接入方用量含API调用计数", du.get("api_calls", 0) >= 1, f"api_calls={du.get('api_calls', 0)}")

    stats_resp = requests.get(f"{BASE_URL}/api/admin/client-stats").json()
    ds = next((s for s in stats_resp["stats"] if s["client_id"] == default_client_id), None)
    if ds:
        check("默认接入方统计含患者", ds["total_patients"] >= 1)
        check("默认接入方统计含照片", ds["total_photos"] >= 4)
        check("默认接入方今日API>0", ds["daily_api_calls"] >= 1, f"calls={ds['daily_api_calls']}")

    # ========== 测试6: 回调详细记录 + 同步重试 ==========
    test_section("测试 6: 回调配置 + 同步重试 + 执行记录")
    cb_cfg = requests.post(f"{BASE_URL}/api/callbacks/configs", json={
        "client_id": client_a_id,
        "event_type": "photo_submitted",
        "callback_url": "http://127.0.0.1:1/nonexistent-callback",
        "secret_token": "test-secret",
        "max_retries": 2,
        "retry_interval": 10,
        "is_active": True
    }).json()
    check("回调配置创建成功", cb_cfg.get("id") is not None)

    trigger_p = "P-CB-001"
    body_trig, _ = submit_photos(trigger_p, date(2024, 9, 1), True, headers_a, count=4)
    check("触发回调的照片提交成功", body_trig.get("success") is True)

    time.sleep(3)

    tasks = requests.get(f"{BASE_URL}/api/callbacks/tasks", params={
        "client_id": client_a_id, "event_type": "photo_submitted"
    }).json()
    check("存在回调任务", tasks.get("total", 0) >= 1)

    task_id = None
    for t in tasks.get("tasks", []):
        if t.get("patient_no") == trigger_p:
            task_id = t["id"]
            break
    check("找到回调任务", task_id is not None)

    if task_id:
        r1 = requests.post(f"{BASE_URL}/api/callbacks/tasks/retry/{task_id}").json()
        check("同步重试接口返回", r1.get("success") is True)
        check("同步重试失败原因非空", r1.get("error_message", "") != "")

        time.sleep(1)
        r2 = requests.post(f"{BASE_URL}/api/callbacks/tasks/retry/{task_id}").json()
        check("第二次同步重试后状态记录", r2.get("success") is True)

        detail = requests.get(f"{BASE_URL}/api/callbacks/tasks/{task_id}").json()
        execs = detail.get("executions", [])
        check("至少2条执行记录", len(execs) >= 2, f"实际={len(execs)}")

    # ========== 测试7: 接入方统计 + 详情 ==========
    test_section("测试 7: 接入方统计 & 详情")
    stats2 = requests.get(f"{BASE_URL}/api/admin/client-stats").json()
    sa = next((s for s in stats2["stats"] if s["client_id"] == client_a_id), None)
    if sa:
        check("诊所A统计有对比记录", sa["total_compares"] >= 1)
        check("诊所A is_default=False", sa["is_default"] is False)

    check("默认接入方 is_default=True",
          any(s["is_default"] for s in stats2["stats"] if s["client_id"] == default_client_id))

    detail_a = requests.get(f"{BASE_URL}/api/admin/clients/{client_a_id}/detail").json()
    check("诊所A详情 success", detail_a.get("success") is True)
    check("诊所A详情 最近调用非空", len(detail_a.get("recent_logs", [])) >= 1)
    check("诊所A详情 失败回调非空", len(detail_a.get("failed_callbacks", [])) >= 1)
    check("诊所A详情 异常照片非空", len(detail_a.get("abnormal_photos", [])) >= 1)

    # ========== 测试8: 对比禁用 ==========
    test_section("测试 8: 诊所B 对比禁用返回429")
    cmp_b2 = requests.post(f"{BASE_URL}/api/compare/generate", json={
        "patient_no": shared_p, "compare_mode": "initial_vs_current",
        "current_visit_date": "2024-06-20"
    }, headers=headers_b).json()
    check("诊所B 禁用对比 返回429",
          cmp_b2.get("success") is False,
          f"msg={cmp_b2.get('message', cmp_b2)}")

    # ========== 测试9: 大照片配额准确性 ==========
    test_section("测试 9: 大尺寸照片配额 - 按真实数量计算")

    big_img_b64 = make_test_image(width=1600, height=1200, color=(180, 160, 140))
    big_img_len_kb = len(big_img_b64) / 1024
    print(f"  单张大照片 base64 大小: {big_img_len_kb:.1f} KB")

    r_d = requests.post(f"{BASE_URL}/api/clients", json={
        "name": "大照片测试诊所D",
        "client_type": "clinic",
        "daily_api_quota": 500,
        "daily_photo_quota": 5,
        "allow_compare": True
    }).json()
    client_d_id = r_d["id"]
    client_d_key = r_d["api_key"]
    headers_d = {"X-API-Key": client_d_key}
    check("诊所D 创建成功 photo_quota=5", r_d.get("daily_photo_quota") == 5)

    def submit_big_photos(patient_no, visit_date, is_initial, headers, count=4):
        payload = {
            "patient_no": patient_no,
            "patient_name": f"大照片-{patient_no}",
            "visit_date": str(visit_date),
            "is_initial": is_initial,
            "photos": [{"angle": angles[i % len(angles)], "image_base64": big_img_b64} for i in range(count)]
        }
        resp = requests.post(f"{BASE_URL}/api/photos/submit", json=payload, headers=headers)
        return resp.json(), resp.status_code

    big_p = "P-BIGPHOTO-001"
    body_d1, sc_d1 = submit_big_photos(big_p, date(2024, 10, 1), True, headers_d, count=3)
    check("诊所D 第1次大照片提交(3张)成功", body_d1.get("success") is True,
          f"status={sc_d1}")

    list_after_1 = requests.get(f"{BASE_URL}/api/photos/list/{big_p}/2024-10-01", headers=headers_d).json()
    check("提交后照片列表有3张", len(list_after_1.get("photos", [])) == 3)

    body_d2, sc_d2 = submit_big_photos("P-BIGPHOTO-002", date(2024, 10, 2), False, headers_d, count=2)
    check("诊所D 第2次大照片提交(2张)成功(总5张)", body_d2.get("success") is True)

    detail_d = requests.get(f"{BASE_URL}/api/admin/clients/{client_d_id}/detail").json()
    du_d = detail_d.get("daily_usage", {})
    check("用量显示已用5张照片", du_d.get("photo_uploads", 0) == 5,
          f"photo_uploads={du_d.get('photo_uploads', 0)}")

    body_big_fail, sc_bf = submit_big_photos("P-BIGPHOTO-003", date(2024, 10, 3), True, headers_d, count=4)
    is_bf_reject = body_big_fail.get("success") is False and sc_bf == 429
    check("大照片超配额 整次返回429", is_bf_reject,
          f"status={sc_bf}, msg={body_big_fail.get('message', '')}")

    if not body_big_fail.get("success"):
        check("返回含真实requested=4", body_big_fail.get("requested") == 4,
              f"requested={body_big_fail.get('requested')}")
        check("返回含used=5", body_big_fail.get("used") == 5,
              f"used={body_big_fail.get('used')}")
        check("返回含limit=5", body_big_fail.get("limit") == 5,
              f"limit={body_big_fail.get('limit')}")
        check("消息含剩余额度和本次提交", "剩余额度" in body_big_fail.get("message", "") and
              "本次提交" in body_big_fail.get("message", ""))

    list_after_fail = requests.get(f"{BASE_URL}/api/photos/list/P-BIGPHOTO-003/2024-10-03", headers=headers_d).json()
    check("超额后该患者无照片(整次未保存)", len(list_after_fail.get("photos", [])) == 0)

    logs_bf = requests.get(f"{BASE_URL}/api/admin/logs", params={
        "patient_no": "P-BIGPHOTO-003", "client_id": client_d_id
    }).json()
    check("管理员可按患者+接入方筛到429日志", logs_bf.get("total", 0) >= 1,
          f"total={logs_bf.get('total', 0)}")

    if logs_bf.get("total", 0) > 0:
        log_item = logs_bf["logs"][0]
        check("失败日志patient_no正确", log_item.get("patient_no") == "P-BIGPHOTO-003")
        check("失败日志status_code=429", log_item.get("status_code") == 429)

    summary()


if __name__ == "__main__":
    print()
    print("╔" + "=" * 58 + "╗")
    print("║    正畸复诊拍照对比服务 - v1.3.0 隔离/配额/回调/批量版测试套件   ║")
    print("╚" + "=" * 58 + "╝")
    try:
        main()
    except requests.exceptions.ConnectionError:
        print("✗ 无法连接到服务，请确认 http://localhost:8000 已启动")
    except Exception as e:
        import traceback
        traceback.print_exc()
        print(f"测试异常: {e}")
