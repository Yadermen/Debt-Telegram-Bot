import pandas as pd
from io import BytesIO
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.database.models import Debt, User
from datetime import datetime
from app.keyboards.texts import tr

async def export_user_debts_to_excel(session, user_id: int) -> BytesIO:
    # Получаем все активные долги
    stmt = select(Debt).where(
        Debt.user_id == user_id,
        Debt.is_active == True
    ).order_by(Debt.created_at.desc())

    result = await session.execute(stmt)
    debts = result.scalars().all()

    # Заголовки через tr
    col_id       = await tr(user_id, 'export_col_id')
    col_person   = await tr(user_id, 'export_col_person')
    col_amount   = await tr(user_id, 'export_col_amount')
    col_currency = await tr(user_id, 'export_col_currency')
    col_type     = await tr(user_id, 'export_col_type')
    col_date     = await tr(user_id, 'export_col_date')
    col_due      = await tr(user_id, 'export_col_due')
    col_comment  = await tr(user_id, 'export_col_comment')
    col_status   = await tr(user_id, 'export_col_status')
    col_created  = await tr(user_id, 'export_col_created')

    type_owe     = await tr(user_id, 'export_type_owe')
    type_owed    = await tr(user_id, 'export_type_owed')
    status_closed= await tr(user_id, 'export_status_closed')
    status_active= await tr(user_id, 'export_status_active')

    sheet_name   = await tr(user_id, 'export_sheet_name')

    # Формируем данные
    data = []
    for debt in debts:
        debt_type = type_owe if debt.direction == "owe" else type_owed
        status    = status_closed if debt.closed else status_active

        data.append({
            col_id: debt.id,
            col_person: debt.person,
            col_amount: debt.amount,
            col_currency: debt.currency,
            col_type: debt_type,
            col_date: debt.date,
            col_due: debt.due,
            col_comment: debt.comment or '',
            col_status: status,
            col_created: debt.created_at.strftime('%d.%m.%Y %H:%M') if debt.created_at else ''
        })

    # Создаём DataFrame
    df = pd.DataFrame(data)

    # Пишем в Excel
    excel_buffer = BytesIO()
    with pd.ExcelWriter(excel_buffer, engine='openpyxl') as writer:
        df.to_excel(writer, sheet_name=sheet_name, index=False)

        worksheet = writer.sheets[sheet_name]
        for column in worksheet.columns:
            max_length = 0
            column_letter = column[0].column_letter
            for cell in column:
                try:
                    if len(str(cell.value)) > max_length:
                        max_length = len(str(cell.value))
                except:
                    pass
            worksheet.column_dimensions[column_letter].width = min(max_length + 2, 50)

    excel_buffer.seek(0)
    return excel_buffer


def get_export_filename(user_id: int) -> str:
    """
    Генерирует имя файла для экспорта

    Args:
        user_id: ID пользователя

    Returns:
        str: Имя файла
    """
    current_date = datetime.now().strftime('%Y%m%d_%H%M%S')
    return f"debts_export_{user_id}_{current_date}.xlsx"


# Альтернативная версия с дополнительной статистикой (ASYNC)
async def export_user_debts_with_stats_to_excel(session: AsyncSession, user_id: int) -> BytesIO:
    """
    Экспортирует долги с дополнительной статистикой (ASYNC версия)
    """

    # Получаем долги
    stmt = select(Debt).where(
        Debt.user_id == user_id,
        Debt.is_active == True
    ).order_by(Debt.created_at.desc())

    result = await session.execute(stmt)
    debts = result.scalars().all()

    # Создаем основные данные
    debt_data = []
    total_owed_to_me = 0  # Сколько мне должны
    total_i_owe = 0  # Сколько я должен

    for debt in debts:
        debt_type = "Я должен" if debt.direction == "owe" else "Мне должны"
        status = "Закрыт" if debt.closed else "Активен"

        # Считаем статистику только для активных долгов
        if not debt.closed:
            if debt.direction == "owed":
                total_owed_to_me += debt.amount
            else:
                total_i_owe += debt.amount

        debt_data.append({
            'ID': debt.id,
            'Человек': debt.person,
            'Сумма': debt.amount,
            'Валюта': debt.currency,
            'Тип долга': debt_type,
            'Дата создания': debt.date,
            'Срок погашения': debt.due,
            'Комментарий': debt.comment or '',
            'Статус': status,
            'Создан': debt.created_at.strftime('%d.%m.%Y %H:%M') if debt.created_at else ''
        })

    # Создаем статистику
    stats_data = [
        {'Показатель': 'Общая сумма долгов мне', 'Значение': total_owed_to_me, 'Валюта': 'UZS'},
        {'Показатель': 'Общая сумма моих долгов', 'Значение': total_i_owe, 'Валюта': 'UZS'},
        {'Показатель': 'Баланс (+ в мою пользу)', 'Значение': total_owed_to_me - total_i_owe, 'Валюта': 'UZS'},
        {'Показатель': 'Всего записей о долгах', 'Значение': len(debt_data), 'Валюта': ''},
        {'Показатель': 'Дата экспорта', 'Значение': datetime.now().strftime('%d.%m.%Y %H:%M'), 'Валюта': ''}
    ]

    # Создаем DataFrames
    df_debts = pd.DataFrame(debt_data)
    df_stats = pd.DataFrame(stats_data)

    # Создаем Excel с несколькими листами
    excel_buffer = BytesIO()

    with pd.ExcelWriter(excel_buffer, engine='openpyxl') as writer:
        # Лист с долгами
        df_debts.to_excel(writer, sheet_name='Долги', index=False)

        # Лист со статистикой
        df_stats.to_excel(writer, sheet_name='Статистика', index=False)

        # Форматируем листы
        for sheet_name in ['Долги', 'Статистика']:
            worksheet = writer.sheets[sheet_name]

            for column in worksheet.columns:
                max_length = 0
                column_letter = column[0].column_letter

                for cell in column:
                    try:
                        if len(str(cell.value)) > max_length:
                            max_length = len(str(cell.value))
                    except:
                        pass

                adjusted_width = min(max_length + 2, 50)
                worksheet.column_dimensions[column_letter].width = adjusted_width

    excel_buffer.seek(0)
    return excel_buffer