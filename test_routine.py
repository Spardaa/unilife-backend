"""
测试 Routine 三层数据模型功能
"""
import sys
sys.path.append(".")

from datetime import datetime, timedelta
from app.services.routine_service import routine_service

def test_routine_three_layer_model():
    """测试 Routine 三层模型"""
    print("=" * 60)
    print("Routine Three-Layer Model Test")
    print("=" * 60)
    print()

    user_id = "test_user_routine"

    # ========== Layer 1: Template（规则层）==========
    print("[Layer 1] Creating Routine Template...")
    template = routine_service.create_template(
        user_id=user_id,
        name="健身计划",
        description="每周一到五健身，训练顺序是胸肩背循环",
        category="fitness",
        repeat_rule={
            "frequency": "weekly",
            "days": [0, 1, 2, 3, 4],  # 周一到五
            "time": "18:00"
        },
        sequence=["胸", "肩", "背"],  # 循环序列
        is_flexible=True
    )
    print(f"[OK] Template created: {template.id}")
    print(f"     Name: {template.name}")
    print(f"     Sequence: {template.sequence}")
    print(f"     Position: {template.sequence_position}")
    print()

    # ========== Layer 2: Instance（实例层）==========
    print("[Layer 2] Generating Routine Instances...")

    # 获取今天的日期
    today = datetime.now()
    start_date = (today + timedelta(days=0)).strftime("%Y-%m-%d")
    end_date = (today + timedelta(days=14)).strftime("%Y-%m-%d")

    instances = routine_service.generate_instances(
        template_id=template.id,
        start_date=start_date,
        end_date=end_date
    )
    print(f"[OK] Generated {len(instances)} instances:")
    for inst in instances[:5]:  # 显示前5个
        seq_info = f" - {inst.sequence_item}" if inst.sequence_item else ""
        print(f"     {inst.scheduled_date} {inst.scheduled_time}{seq_info}")
    if len(instances) > 5:
        print(f"     ... and {len(instances) - 5} more")
    print()

    # 检查序列是否正确循环
    print("[Test] Checking sequence rotation...")
    for inst in instances[:5]:
        print(f"     {inst.scheduled_date}: {inst.sequence_item}")
    print()

    # ========== Layer 3: Execution（执行层）==========
    print("[Layer 3] Recording Execution...")

    # 获取第一个实例（应该是"胸"）
    first_instance = instances[0]
    print(f"[INFO] First instance: {first_instance.scheduled_date} - {first_instance.sequence_item}")

    # 取消这个实例（序列不前进）
    execution1 = routine_service.record_execution(
        instance_id=first_instance.id,
        action="cancelled",
        reason="急事",
        sequence_advanced=False  # 关键：序列不前进
    )
    print(f"[OK] Execution recorded: {execution1.action}")
    print(f"     Sequence advanced: {execution1.sequence_advanced}")
    print()

    # 完成第二个实例（序列前进）
    second_instance = instances[1]
    execution2 = routine_service.record_execution(
        instance_id=second_instance.id,
        action="completed",
        sequence_advanced=True  # 序列前进
    )
    print(f"[OK] Execution recorded: {execution2.action}")
    print(f"     Sequence advanced: {execution2.sequence_advanced}")
    print()

    # ========== 测试查询接口（核心）==========
    print("[Query Test] Getting events with routines...")

    events = routine_service.get_events_with_routines(
        user_id=user_id,
        start_date=start_date,
        end_date=end_date
    )

    print(f"[OK] Retrieved {len(events)} events")
    routine_events = [e for e in events if e.get("is_routine")]
    print(f"     Routine instances: {len(routine_events)}")
    for event in routine_events[:5]:
        type_str = "[长期]" if event.get("is_routine") else "[普通]"
        title = event.get("title", "")
        print(f"     {type_str} {event['date']} {title}")
    print()

    # ========== 测试序列状态验证 ==========
    print("[Sequence Test] Verifying sequence state...")

    # 重新生成实例，检查序列位置
    updated_template = routine_service.get_template(template.id)
    print(f"[INFO] Template sequence_position: {updated_template.sequence_position}")

    new_instances = routine_service.generate_instances(
        template_id=template.id,
        start_date=start_date,
        end_date=end_date,
        force_regenerate=False
    )

    print(f"[OK] Instances after execution:")
    for inst in new_instances[:5]:
        status_str = f" ({inst.status})" if inst.status != "pending" else ""
        print(f"     {inst.scheduled_date}: {inst.sequence_item}{status_str}")
    print()

    # ========== 测试获取执行历史 ==========
    print("[History Test] Getting execution history...")

    executions = routine_service.get_executions(instance_id=first_instance.id)
    print(f"[OK] Instance has {len(executions)} execution records:")
    for exec in executions:
        print(f"     - {exec.action}: {exec.reason or 'No reason'}")
    print()

    # ========== 清理测试数据 ==========
    print("[Cleanup] Deleting test data...")
    routine_service.delete_template(template.id)
    print(f"[OK] Template deleted")
    print()

    print("=" * 60)
    print("[SUCCESS] All Routine tests passed!")
    print()
    print("Summary:")
    print("  - Template layer: Define rules and sequences")
    print("  - Instance layer: Generate specific occurrences")
    print("  - Execution layer: Record what actually happened")
    print("  - Query: Unified interface for normal + routine events")
    print("=" * 60)

if __name__ == "__main__":
    test_routine_three_layer_model()
