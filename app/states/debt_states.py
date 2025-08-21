# states/debt_states.py
from aiogram.fsm.state import StatesGroup, State

class AddDebt(StatesGroup):
    person = State()
    currency = State()
    amount = State()
    due = State()
    direction = State()
    comment = State()

class EditDebt(StatesGroup):
    edit_value = State()
    extend_due = State()

    @dp.callback_query(lambda c: c.data == 'add_debt')
    async def add_debt_start(call: CallbackQuery, state: FSMContext):
        await state.clear()
        await call.message.edit_text(await tr(call.from_user.id, 'person'))
        await state.set_state(AddDebt.person)

    @dp.message(AddDebt.person)
    async def add_debt_person(message: Message, state: FSMContext):
        await state.update_data(person=message.text)
        await message.answer(await tr(message.from_user.id, 'currency'),
                             reply_markup=await currency_keyboard(message.from_user.id))
        await state.set_state(AddDebt.currency)

    @dp.callback_query(lambda c: c.data.startswith('cur_'), AddDebt.currency)
    async def add_debt_currency(call: CallbackQuery, state: FSMContext):
        currency = call.data.split('_')[1].upper()
        await state.update_data(currency=currency)
        await call.message.edit_text(await tr(call.from_user.id, 'amount'))
        await state.set_state(AddDebt.amount)

    @dp.message(AddDebt.amount)
    async def add_debt_amount(message: Message, state: FSMContext):
        if not message.text.isdigit():
            await message.answer(await tr(message.from_user.id, 'amount_wrong'))
            return
        await state.update_data(amount=int(message.text))
        suggest_date = (datetime.now() + timedelta(days=7)).strftime('%Y-%m-%d')
        await message.answer(await tr(message.from_user.id, 'due', suggest_date=suggest_date))
        await state.set_state(AddDebt.due)

    @dp.message(AddDebt.due)
    async def add_debt_due(message: Message, state: FSMContext):
        try:
            datetime.strptime(message.text, '%Y-%m-%d')
        except Exception:
            suggest_date = (datetime.now() + timedelta(days=7)).strftime('%Y-%m-%d')
            await message.answer(await tr(message.from_user.id, 'due_wrong', suggest_date=suggest_date))
            return
        await state.update_data(due=message.text)
        await message.answer(await tr(message.from_user.id, 'direction'),
                             reply_markup=await direction_keyboard(message.from_user.id))
        await state.set_state(AddDebt.direction)

    @dp.callback_query(lambda c: c.data.startswith('dir_'), AddDebt.direction)
    async def add_debt_direction(call: CallbackQuery, state: FSMContext):
        direction = 'gave' if call.data == 'dir_gave' else 'took'
        await state.update_data(direction=direction)
        await call.message.edit_text(await tr(call.from_user.id, 'comment'),
                                     reply_markup=await skip_comment_keyboard(call.from_user.id))
        await state.set_state(AddDebt.comment)

    @dp.message(AddDebt.comment)
    async def add_debt_comment(message: Message, state: FSMContext):
        data = await state.get_data()
        debt = {
            'person': data['person'],
            'amount': data['amount'],
            'currency': data.get('currency', 'UZS'),
            'direction': data['direction'],
            'date': datetime.now().strftime('%Y-%m-%d'),
            'due': data['due'],
            'comment': message.text if message.text.strip() else '',
            'closed': False
        }
        await add_debt(int(message.from_user.id), debt)
        await message.answer(await tr(message.from_user.id, 'debt_saved'),
                             reply_markup=await main_menu(message.from_user.id))
        await state.clear()

    @dp.callback_query(lambda c: c.data == 'skip_comment', AddDebt.comment)
    async def skip_comment(call: CallbackQuery, state: FSMContext):
        data = await state.get_data()
        debt = {
            'person': data['person'],
            'amount': data['amount'],
            'currency': data.get('currency', 'UZS'),
            'direction': data['direction'],
            'date': datetime.now().strftime('%Y-%m-%d'),
            'due': data['due'],
            'comment': '',
            'closed': False
        }
        await add_debt(int(call.from_user.id), debt)
        await call.message.edit_text(await tr(call.from_user.id, 'debt_saved'),
                                     reply_markup=await main_menu(call.from_user.id))
        await state.clear()

    # --- Возврат в главное меню ---
    @dp.callback_query(lambda c: c.data == 'back_main')
    async def back_main(call: CallbackQuery, state: FSMContext):
        await state.clear()
        text = await tr(call.from_user.id, 'choose_action')
        markup = await main_menu(call.from_user.id)

        await safe_edit_message(call, text, markup)

    import html

    def safe_str(s):
        if s is None:
            return ''
        return html.escape(str(s))

    # --- Просмотр долгов пользователя ---
    # --- Обновлённый обработчик списка долгов с первой страницей ---
    @dp.callback_query(lambda c: c.data == 'my_debts')
    async def show_debts(call: CallbackQuery, state: FSMContext):
        user_id = call.from_user.id
        try:
            debts = await get_open_debts(user_id)
        except Exception:
            await call.message.answer(await tr(user_id, 'db_error'))
            return
        if not debts:
            text = await tr(user_id, 'no_debts')
            markup = await main_menu(user_id)
            await safe_edit_message(call, text, markup)
            return
        text = await tr(user_id, 'your_debts')
        markup = await debts_list_keyboard_paginated(debts, user_id, page=0)
        await safe_edit_message(call, text, markup)