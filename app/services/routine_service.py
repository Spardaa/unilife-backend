"""
Routine Service - 长期重复日程服务
实现三层数据模型的业务逻辑
"""
from typing import Dict, Any, List, Optional
from datetime import datetime, timedelta
from sqlalchemy import create_engine, desc, and_, or_, text
from sqlalchemy.orm import sessionmaker, Session, joinedload
from sqlalchemy.pool import StaticPool
from dateutil.parser import parse
from dateutil.rrule import rrule, rruleset, rrulestr
from dateutil.relativedelta import relativedelta
import json

from app.models.routine import RoutineTemplate, RoutineInstance, RoutineExecution, RoutineMemory, Base
from app.config import settings


class RoutineService:
    """长期重复日程服务"""

    def __init__(self, db_path: str = None):
        """初始化服务"""
        if db_path is None:
            db_path = settings.database_url.replace("sqlite:///", "")

        self.engine = create_engine(
            f"sqlite:///{db_path}",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
            echo=False
        )

        Base.metadata.create_all(self.engine)
        self.SessionLocal = sessionmaker(
            autocommit=False,
            autoflush=False,
            bind=self.engine
        )

    def get_session(self) -> Session:
        """获取数据库会话"""
        return self.SessionLocal()

    # ==================== Template 管理 ====================

    def create_template(
        self,
        user_id: str,
        name: str,
        repeat_rule: Dict[str, Any],
        sequence: Optional[List[str]] = None,
        description: Optional[str] = None,
        category: Optional[str] = None,
        is_flexible: bool = True,
        preferred_time_slots: Optional[List[Dict[str, str]]] = None,
        makeup_strategy: str = "skip"
    ) -> RoutineTemplate:
        """
        创建 Routine 模板

        Args:
            user_id: 用户ID
            name: 名称
            repeat_rule: 重复规则 JSON
            sequence: 序列列表（可选）
            description: 描述
            category: 分类
            is_flexible: 是否灵活
            preferred_time_slots: 偏好时间段
            makeup_strategy: 补偿策略

        Returns:
            RoutineTemplate 对象
        """
        db = self.get_session()
        try:
            template = RoutineTemplate(
                user_id=user_id,
                name=name,
                description=description,
                category=category,
                repeat_rule=repeat_rule,
                sequence=sequence,
                sequence_position=0,
                is_flexible=is_flexible,
                preferred_time_slots=preferred_time_slots,
                makeup_strategy=makeup_strategy,
                active=True
            )
            db.add(template)
            db.commit()
            db.refresh(template)
            return template
        finally:
            db.close()

    def get_template(self, template_id: str) -> Optional[RoutineTemplate]:
        """获取模板"""
        db = self.get_session()
        try:
            return db.query(RoutineTemplate).filter(
                RoutineTemplate.id == template_id
            ).first()
        finally:
            db.close()

    def list_templates(
        self,
        user_id: str,
        active_only: bool = True
    ) -> List[RoutineTemplate]:
        """列出用户的模板"""
        db = self.get_session()
        try:
            query = db.query(RoutineTemplate).filter(
                RoutineTemplate.user_id == user_id
            )
            if active_only:
                query = query.filter(RoutineTemplate.active == True)
            return query.order_by(desc(RoutineTemplate.created_at)).all()
        finally:
            db.close()

    def update_template(
        self,
        template_id: str,
        **updates
    ) -> bool:
        """更新模板"""
        db = self.get_session()
        try:
            template = db.query(RoutineTemplate).filter(
                RoutineTemplate.id == template_id
            ).first()
            if not template:
                return False

            for key, value in updates.items():
                if hasattr(template, key):
                    setattr(template, key, value)

            db.commit()
            return True
        finally:
            db.close()

    def delete_template(self, template_id: str) -> bool:
        """删除模板（级联删除所有实例和执行记录）"""
        db = self.get_session()
        try:
            result = db.query(RoutineTemplate).filter(
                RoutineTemplate.id == template_id
            ).delete()
            db.commit()
            return result > 0
        finally:
            db.close()

    # ==================== Instance 管理 ====================

    def generate_instances(
        self,
        template_id: str,
        start_date: str,
        end_date: str,
        force_regenerate: bool = False
    ) -> List[RoutineInstance]:
        """
        生成指定时间范围内的实例

        Args:
            template_id: 模板ID
            start_date: 开始日期 (YYYY-MM-DD)
            end_date: 结束日期 (YYYY-MM-DD)
            force_regenerate: 是否强制重新生成

        Returns:
            生成的实例列表
        """
        template = self.get_template(template_id)
        if not template:
            return []

        db = self.get_session()
        try:
            # 解析重复规则，生成日期列表
            dates = self._calculate_repeat_dates(
                template.repeat_rule,
                start_date,
                end_date
            )

            instances = []
            for date in dates:
                date_str = date.strftime("%Y-%m-%d")

                # 检查是否已存在
                existing = db.query(RoutineInstance).filter(
                    and_(
                        RoutineInstance.template_id == template_id,
                        RoutineInstance.scheduled_date == date_str
                    )
                ).first()

                if existing and not force_regenerate:
                    instances.append(existing)
                    continue

                if existing and force_regenerate:
                    db.delete(existing)

                # 确定这次的序列项
                sequence_item = None
                if template.sequence:
                    seq_len = len(template.sequence)
                    sequence_item = template.sequence[template.sequence_position % seq_len]

                # 创建新实例
                instance = RoutineInstance(
                    template_id=template_id,
                    scheduled_date=date_str,
                    scheduled_time=template.repeat_rule.get("time"),
                    sequence_item=sequence_item,
                    status="pending"
                )
                db.add(instance)
                instances.append(instance)

                # 更新模板的序列位置
                if template.sequence:
                    template.sequence_position += 1

            db.commit()

            # 刷新实例
            for inst in instances:
                db.refresh(inst)

            return instances
        finally:
            db.close()

    def _calculate_repeat_dates(
        self,
        repeat_rule: Dict[str, Any],
        start_date: str,
        end_date: str
    ) -> List[datetime]:
        """
        根据重复规则计算日期列表

        Args:
            repeat_rule: 重复规则
            start_date: 开始日期
            end_date: 结束日期

        Returns:
            日期列表
        """
        start = parse(start_date).date()
        end = parse(end_date).date()

        frequency = repeat_rule.get("frequency", "daily")

        if frequency == "daily":
            # 每天重复
            dates = [start + timedelta(days=i) for i in range((end - start).days + 1)]

        elif frequency == "weekly":
            # 每周特定几天
            days = repeat_rule.get("days", [])  # [0, 1, 2] = 周一、周二、周三
            dates = []
            current = start
            while current <= end:
                if current.weekday() in days:
                    dates.append(current)
                current += timedelta(days=1)

        elif frequency == "monthly":
            # 每月特定日期
            month_days = repeat_rule.get("days", [])  # [1, 15] = 每月1号和15号
            dates = []
            current = start
            while current <= end:
                if current.day in month_days:
                    dates.append(current)
                current += timedelta(days=1)

        else:
            # 默认为每天
            dates = [start + timedelta(days=i) for i in range((end - start).days + 1)]

        return dates

    def _generate_habit_instances(
        self,
        habit_event: Any,
        start_date: str,
        end_date: str
    ) -> List[Dict[str, Any]]:
        """
        从 events 表的 HABIT 记录生成指定日期范围的实例

        Args:
            habit_event: events 表中的 HABIT 类型记录
            start_date: 查询开始日期 (YYYY-MM-DD)
            end_date: 查询结束日期 (YYYY-MM-DD)

        Returns:
            实例列表（字典格式，与 RoutineInstance.to_event_format() 兼容）
        """
        repeat_rule = habit_event.repeat_rule
        if not repeat_rule:
            return []

        # 计算日期范围
        dates = self._calculate_repeat_dates(
            repeat_rule=repeat_rule,
            start_date=start_date,
            end_date=end_date
        )

        instances = []
        for date in dates:
            date_str = date.strftime("%Y-%m-%d")

            # 检查是否已完成（从 routine_completed_dates 字段）
            completed_dates = habit_event.routine_completed_dates or []
            if date_str in completed_dates:
                status = "completed"
            else:
                status = "pending"

            # 获取时间（如果有）
            time_str = None
            if isinstance(repeat_rule, dict):
                time_str = repeat_rule.get("time")

            # 构建实例（兼容 to_event_format() 格式的字典）
            instance = {
                "id": f"{habit_event.id}_{date_str}",  # 生成虚拟实例ID
                "template_id": habit_event.id,
                "scheduled_date": date_str,
                "scheduled_time": time_str,
                "title": habit_event.title,
                "description": habit_event.description,
                "status": status,
                "is_routine": True,
                "source": "events_table"  # 标记来源
            }
            instances.append(instance)

        return instances

    def get_instances(
        self,
        template_id: Optional[str] = None,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        status: Optional[str] = None,
        limit: int = 100
    ) -> List[RoutineInstance]:
        """获取实例列表"""
        db = self.get_session()
        try:
            query = db.query(RoutineInstance)

            if template_id:
                query = query.filter(RoutineInstance.template_id == template_id)
            if start_date:
                query = query.filter(RoutineInstance.scheduled_date >= start_date)
            if end_date:
                query = query.filter(RoutineInstance.scheduled_date <= end_date)
            if status:
                query = query.filter(RoutineInstance.status == status)

            return query.order_by(RoutineInstance.scheduled_date).limit(limit).all()
        finally:
            db.close()

    def get_instance(self, instance_id: str, load_template: bool = True) -> Optional[RoutineInstance]:
        """
        获取单个实例

        Args:
            instance_id: 实例ID
            load_template: 是否预加载 template 关联（默认 True，避免 session 关闭后无法访问）
        """
        db = self.get_session()
        try:
            query = db.query(RoutineInstance).filter(
                RoutineInstance.id == instance_id
            )
            # 预加载 template 关联，避免 session 关闭后 lazy load 失败
            if load_template:
                query = query.options(joinedload(RoutineInstance.template))
            return query.first()
        finally:
            db.close()

    # ==================== Execution 管理 ====================

    def record_execution(
        self,
        instance_id: str,
        action: str,
        reason: Optional[str] = None,
        notes: Optional[str] = None,
        actual_date: Optional[str] = None,
        actual_time: Optional[str] = None,
        sequence_advanced: bool = True
    ) -> RoutineExecution:
        """
        记录执行动作

        Args:
            instance_id: 实例ID
            action: 动作类型
            reason: 原因
            notes: 备注
            actual_date: 实际执行日期
            actual_time: 实际执行时间
            sequence_advanced: 序列是否前进

        Returns:
            RoutineExecution 对象
        """
        db = self.get_session()
        try:
            # 创建执行记录
            execution = RoutineExecution(
                instance_id=instance_id,
                action=action,
                reason=reason,
                notes=notes,
                actual_date=actual_date,
                actual_time=actual_time,
                sequence_advanced=sequence_advanced
            )
            db.add(execution)

            # 更新实例状态
            instance = db.query(RoutineInstance).filter(
                RoutineInstance.id == instance_id
            ).first()
            if instance:
                if action == "completed":
                    instance.status = "completed"
                elif action == "cancelled":
                    instance.status = "cancelled"
                elif action == "rescheduled":
                    instance.status = "rescheduled"
                elif action == "skipped":
                    instance.status = "skipped"

                # 更新模板统计
                template = db.query(RoutineTemplate).filter(
                    RoutineTemplate.id == instance.template_id
                ).first()
                if template and action == "completed":
                    template.completed_instances += 1

            db.commit()
            db.refresh(execution)
            return execution
        finally:
            db.close()

    def get_executions(self, instance_id: str) -> List[RoutineExecution]:
        """获取实例的执行记录"""
        db = self.get_session()
        try:
            return db.query(RoutineExecution).filter(
                RoutineExecution.instance_id == instance_id
            ).order_by(desc(RoutineExecution.created_at)).all()
        finally:
            db.close()

    # ==================== 查询接口（核心）====================

    def get_events_with_routines(
        self,
        user_id: str,
        start_date: str,
        end_date: str
    ) -> List[Dict[str, Any]]:
        """
        获取指定时间范围内的事件（普通 + Routine）

        这是主要查询接口，返回统一格式的事件列表

        支持两套数据源：
        1. events 表中的普通事件（有 start_time）
        2. events 表中的 HABIT 类型长期日程（event_type='HABIT', repeat_rule IS NOT NULL）
        3. routine_templates 表中的三层架构模板

        Args:
            user_id: 用户ID
            start_date: 开始日期
            end_date: 结束日期

        Returns:
            事件列表，每个事件包含 is_routine 标记
        """
        from sqlalchemy import text
        # Import EventModel for querying HABIT events
        from app.services.db import EventModel
        db = self.get_session()
        try:
            # 1. 获取普通事件（使用原生 SQL）
            start_datetime = f"{start_date}T00:00:00"
            end_datetime = f"{end_date}T23:59:59"

            query = text("""
                SELECT id, user_id, title, description, start_time, end_time,
                       duration, category, status, location, tags
                FROM events
                WHERE user_id = :user_id
                  AND start_time >= :start_time
                  AND start_time <= :end_time
                  AND status != 'cancelled'
                ORDER BY start_time
            """)

            result = db.execute(query, {
                "user_id": user_id,
                "start_time": start_datetime,
                "end_time": end_datetime
            })

            normal_events_data = []
            for row in result:
                normal_events_data.append({
                    "id": row[0],
                    "title": row[2],
                    "description": row[3],
                    "start_time": row[4],
                    "end_time": row[5],
                    "duration": row[6],
                    "category": row[7],
                    "status": row[8],
                    "location": row[9],
                    "tags": row[10] if row[10] else []
                })

            # 2. 【新增】查询 events 表中的 HABIT 类型（旧系统数据）
            habit_events = db.query(EventModel).filter(
                and_(
                    EventModel.user_id == user_id,
                    EventModel.event_type == "HABIT",
                    EventModel.repeat_rule.is_not(None),
                    EventModel.status != "cancelled"
                )
            ).all()

            # 3. 为查询日期范围生成 habit 实例
            routine_instances = []
            for habit in habit_events:
                instances = self._generate_habit_instances(
                    habit_event=habit,
                    start_date=start_date,
                    end_date=end_date
                )
                routine_instances.extend(instances)

            # 4. 获取所有激活的 Routine 模板（新系统，向后兼容）
            templates = db.query(RoutineTemplate).filter(
                and_(
                    RoutineTemplate.user_id == user_id,
                    RoutineTemplate.active == True
                )
            ).all()

            # 5. 为每个模板生成实例
            for template in templates:
                instances = self.generate_instances(
                    template_id=template.id,
                    start_date=start_date,
                    end_date=end_date
                )
                routine_instances.extend(instances)

            # 4. 合并并排序
            events = []

            # 添加普通事件
            for event in normal_events_data:
                events.append({
                    "id": event.get("id"),
                    "type": "normal",
                    "title": event.get("title"),
                    "start_time": event.get("start_time"),
                    "is_routine": False,
                    "metadata": event.get("metadata")
                })

            # 添加 Routine 实例
            for instance in routine_instances:
                # 处理两种类型的实例：
                # 1. RoutineInstance 对象（来自 routine_templates 表）
                # 2. dict 字典（来自 events 表的 HABIT 类型）
                if isinstance(instance, dict):
                    # dict 类型实例（来自 events 表）
                    status = instance.get("status", "pending")
                    if status != "cancelled":  # 不显示已取消的
                        # 将 dict 转换为 event 格式
                        event_format = {
                            "id": instance.get("id"),
                            "type": "routine_instance",
                            "template_id": instance.get("template_id"),
                            "title": instance.get("title"),
                            "date": instance.get("scheduled_date"),
                            "time": instance.get("scheduled_time"),
                            "status": status,
                            "is_routine": True,
                            "source": instance.get("source", "events_table")
                        }
                        events.append(event_format)
                else:
                    # RoutineInstance 对象（来自 routine_templates 表）
                    if instance.status != "cancelled":  # 不显示已取消的
                        events.append(instance.to_event_format())

            # 按日期和时间排序
            def sort_key(event):
                if event.get("is_routine"):
                    return (event["date"], event.get("time", "00:00"))
                else:
                    # 普通事件使用 start_time
                    start_time = event.get("start_time", "")
                    if start_time:
                        # 从 ISO 格式提取日期和时间
                        try:
                            dt = datetime.fromisoformat(start_time)
                            return (dt.date().isoformat(), dt.time().isoformat())
                        except:
                            pass
                    return ("9999-12-31", "23:59")

            events.sort(key=sort_key)

            return events
        finally:
            db.close()

    # ==================== Memory 管理 ====================

    def learn_pattern(
        self,
        template_id: str,
        memory_type: str,
        pattern: Dict[str, Any]
    ) -> RoutineMemory:
        """学习或更新模式"""
        db = self.get_session()
        try:
            # 检查是否已存在相似的记忆
            existing = db.query(RoutineMemory).filter(
                and_(
                    RoutineMemory.template_id == template_id,
                    RoutineMemory.memory_type == memory_type
                )
            ).first()

            if existing:
                # 更新置信度
                existing.pattern = pattern
                existing.updated_at = datetime.utcnow()
                db.commit()
                db.refresh(existing)
                return existing
            else:
                # 创建新记忆
                memory = RoutineMemory(
                    template_id=template_id,
                    memory_type=memory_type,
                    pattern=pattern
                )
                db.add(memory)
                db.commit()
                db.refresh(memory)
                return memory
        finally:
            db.close()

    def get_memories(self, template_id: str) -> List[RoutineMemory]:
        """获取模板的所有记忆"""
        db = self.get_session()
        try:
            return db.query(RoutineMemory).filter(
                RoutineMemory.template_id == template_id
            ).order_by(desc(RoutineMemory.updated_at)).all()
        finally:
            db.close()

    def check_pattern_suggestions(
        self,
        template_id: str,
        context: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """
        检查是否有匹配的模式建议

        Args:
            template_id: 模板ID
            context: 上下文（如：今天是周二，用户要取消）

        Returns:
            建议列表
        """
        memories = self.get_memories(template_id)
        suggestions = []

        for memory in memories:
            # 更新命中次数
            memory.hit_count += 1
            memory.last_triggered_at = datetime.utcnow()

            # 检查是否匹配
            pattern = memory.pattern
            confidence = pattern.get("confidence", 0)

            if confidence >= 0.7:  # 置信度 > 70%
                suggestion = pattern.get("suggestion")
                if suggestion:
                    suggestions.append({
                        "memory_id": memory.id,
                        "suggestion": suggestion,
                        "confidence": confidence,
                        "pattern_type": memory.memory_type
                    })

        return suggestions


# 全局服务实例
routine_service = RoutineService()
