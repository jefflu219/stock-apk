import sqlite3
from datetime import datetime, timedelta
from kivy.app import App
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.button import Button
from kivy.uix.label import Label
from kivy.uix.textinput import TextInput
from kivy.uix.spinner import Spinner
from kivy.uix.scrollview import ScrollView
from kivy.uix.gridlayout import GridLayout
from kivy.uix.popup import Popup
from kivy.uix.screenmanager import ScreenManager, Screen
from kivy.properties import ObjectProperty, StringProperty, NumericProperty
from kivy.core.window import Window
from kivy.metrics import dp

Window.size = (400, 700)  # 适合手机竖屏

DB_NAME = "portfolio.db"

def init_db():
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS assets (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        code TEXT UNIQUE NOT NULL,
        name TEXT NOT NULL,
        type TEXT NOT NULL CHECK(type IN ('股票','基金')))''')
    c.execute('''CREATE TABLE IF NOT EXISTS transactions (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        asset_id INTEGER NOT NULL,
        date TEXT NOT NULL,
        trans_type TEXT NOT NULL CHECK(trans_type IN ('买入','卖出')),
        price REAL NOT NULL,
        quantity REAL NOT NULL,
        fee REAL DEFAULT 0,
        account TEXT DEFAULT '初首' CHECK(account IN ('初首','累计')),
        FOREIGN KEY (asset_id) REFERENCES assets(id))''')
    c.execute('''CREATE TABLE IF NOT EXISTS prices (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        asset_id INTEGER NOT NULL,
        date TEXT NOT NULL,
        price REAL NOT NULL,
        FOREIGN KEY (asset_id) REFERENCES assets(id),
        UNIQUE(asset_id, date))''')
    try:
        c.execute("SELECT account FROM transactions LIMIT 1")
    except sqlite3.OperationalError:
        c.execute("ALTER TABLE transactions ADD COLUMN account TEXT DEFAULT '初首' CHECK(account IN ('初首','累计'))")
    conn.commit()
    conn.close()

# ---------- 业务逻辑函数（与 V2.6 完全一致） ----------
def get_holdings():
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute("SELECT id, code, name, type FROM assets")
    assets = c.fetchall()
    holdings = []
    for a in assets:
        aid, code, name, atype = a
        c.execute("SELECT trans_type, price, quantity, fee FROM transactions WHERE asset_id=? ORDER BY date, id", (aid,))
        trans = c.fetchall()
        q, cost, avg = 0, 0, 0
        for t_type, prc, qty, fee in trans:
            if t_type == '买入':
                cost += prc * qty + (fee or 0)
                q += qty
                avg = cost / q if q else 0
            else:
                cost -= avg * qty
                q -= qty
                if q < 0:
                    q = 0; cost = 0; avg = 0
        if q <= 0:
            continue
        c.execute("SELECT account, SUM(CASE WHEN trans_type='买入' THEN quantity ELSE -quantity END) FROM transactions WHERE asset_id=? GROUP BY account", (aid,))
        acc_qty = {'初首': 0, '累计': 0}
        for row in c.fetchall():
            acc_qty[row[0]] = row[1] if row[1] else 0
        c.execute("SELECT price FROM prices WHERE asset_id=? ORDER BY date DESC LIMIT 1", (aid,))
        row = c.fetchone()
        latest = row[0] if row else 0.0
        mv = q * latest
        pl = mv - cost
        chg = ((latest - avg) / avg * 100) if avg else 0
        cost_diff = latest - avg
        holdings.append({
            'id': aid, 'code': code, 'name': name, 'type': atype,
            'init_qty': round(acc_qty['初首'], 2),
            'acc_qty': round(acc_qty['累计'], 2),
            'hold_qty': round(q, 2),
            'avg_cost': round(avg, 4),
            'latest_price': latest,
            'market_value': round(mv, 2),
            'cost_total': round(cost, 2),
            'unrealized_pl': round(pl, 2),
            'change_pct': round(chg, 2),
            'cost_diff': round(cost_diff, 2)
        })
    conn.close()
    return holdings

def get_history():
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute("""SELECT a.code, a.name, t.date, t.trans_type, t.price, t.quantity, t.fee,
                 (t.price*t.quantity) AS amount, t.asset_id, t.id, t.account
                 FROM transactions t JOIN assets a ON t.asset_id=a.id ORDER BY t.date, t.id""")
    rows = c.fetchall()
    history = []
    for row in rows:
        profit = 0.0
        if row[3] == '卖出':
            c.execute("SELECT trans_type, price, quantity, fee FROM transactions WHERE asset_id=? AND date<=? AND id<? ORDER BY date, id",
                      (row[8], row[2], row[9]))
            pre_trans = c.fetchall()
            q, cost, avg = 0, 0, 0
            for t in pre_trans:
                if t[0] == '买入':
                    cost += t[1]*t[2] + (t[3] or 0)
                    q += t[2]
                    avg = cost/q if q else 0
                else:
                    cost -= avg*t[2]
                    q -= t[2]
                    if q<0: q=0; cost=0; avg=0
            profit = row[7] - avg*row[4]
        history.append({
            'date': row[2], 'code': row[0], 'name': row[1], 'type': row[3],
            'price': row[4], 'qty': row[5], 'fee': row[6], 'amount': row[7],
            'profit': round(profit,2), 'account': row[10]
        })
    conn.close()
    return history

def add_asset(code, name, atype):
    conn = sqlite3.connect(DB_NAME)
    try:
        conn.execute("INSERT INTO assets (code, name, type) VALUES (?,?,?)", (code, name, atype))
        conn.commit()
    except sqlite3.IntegrityError:
        raise ValueError("代码已存在")
    finally:
        conn.close()

def add_transaction(asset_id, date, trans_type, price, quantity, fee=0, account='初首'):
    conn = sqlite3.connect(DB_NAME)
    conn.execute("INSERT INTO transactions (asset_id, date, trans_type, price, quantity, fee, account) VALUES (?,?,?,?,?,?,?)",
                 (asset_id, date, trans_type, price, quantity, fee, account))
    conn.commit()
    conn.close()

def add_price(asset_id, date, price):
    conn = sqlite3.connect(DB_NAME)
    conn.execute("INSERT OR REPLACE INTO prices (asset_id, date, price) VALUES (?,?,?)", (asset_id, date, price))
    conn.commit()
    conn.close()

def get_assets():
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute("SELECT id, code, name, type FROM assets ORDER BY code")
    assets = c.fetchall()
    conn.close()
    return assets

def get_latest_price(asset_id):
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute("SELECT price FROM prices WHERE asset_id=? ORDER BY date DESC LIMIT 1", (asset_id,))
    row = c.fetchone()
    conn.close()
    return row[0] if row else 0.0

def get_account_holdings(asset_id):
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute("SELECT account, SUM(CASE WHEN trans_type='买入' THEN quantity ELSE -quantity END) FROM transactions WHERE asset_id=? GROUP BY account", (asset_id,))
    result = {'初首':0, '累计':0}
    for row in c.fetchall():
        result[row[0]] = row[1] if row[1] else 0
    conn.close()
    return result['初首'], result['累计']

# ---------- Kivy UI 界面 ----------
class MainScreen(Screen):
    def on_enter(self):
        self.refresh()

    def refresh(self):
        self.ids.hold_container.clear_widgets()
        holdings = get_holdings()
        for h in holdings:
            color = (1,0,0,1) if h['cost_diff'] > 0 else (0,1,0,1) if h['cost_diff'] < 0 else (1,1,1,1)
            self.ids.hold_container.add_widget(Label(
                text=f"[{h['code']}] {h['name']}\n初:{h['init_qty']} | 累:{h['acc_qty']} | 总:{h['hold_qty']}\n成本:{h['avg_cost']} | 价差:{h['cost_diff']:+.2f} | 盈亏:{h['unrealized_pl']}",
                color=color, size_hint_y=None, height=dp(80), halign='center', valign='middle'))
            self.ids.hold_container.add_widget(Label(text=" ", size_hint_y=None, height=dp(10)))

    def go_summary(self):
        summary = ""
        hs = get_holdings()
        total_init = sum(h['init_qty'] for h in hs)
        total_acc = sum(h['acc_qty'] for h in hs)
        total_qty = sum(h['hold_qty'] for h in hs)
        total_cost = sum(h['cost_total'] for h in hs)
        total_mv = sum(h['market_value'] for h in hs)
        total_upl = sum(h['unrealized_pl'] for h in hs)
        avg = total_cost / total_qty if total_qty else 0
        summary = f"初首:{total_init:.2f}\n累计:{total_acc:.2f}\n总持仓:{total_qty:.2f}\n成本:{total_cost:.2f}\n市值:{total_mv:.2f}\n盈亏:{total_upl:.2f}\n均价:{avg:.4f}"
        popup = Popup(title="盈亏总览", content=Label(text=summary), size_hint=(0.8, 0.6))
        popup.open()

class TradeScreen(Screen):
    asset_id = NumericProperty(0)

    def on_enter(self):
        self.update_asset_list()

    def update_asset_list(self):
        assets = get_assets()
        self.ids.asset_spinner.values = [f"{a[0]} {a[1]} {a[2]}" for a in assets]
        if assets:
            self.ids.asset_spinner.text = self.ids.asset_spinner.values[0]

    def submit_trade(self):
        try:
            # 从 spinner 获取资产 id
            selected = self.ids.asset_spinner.text
            asset_id = int(selected.split()[0])
            date = self.ids.date_input.text
            # 初首
            i_type = self.ids.init_type.text
            i_price = float(self.ids.init_price.text or '0')
            i_qty = float(self.ids.init_qty.text or '0')
            i_fee = float(self.ids.init_fee.text or '0')
            if i_qty > 0:
                add_transaction(asset_id, date, i_type, i_price, i_qty, i_fee, '初首')
            # 累计
            a_type = self.ids.acc_type.text
            a_price = float(self.ids.acc_price.text or '0')
            a_qty = float(self.ids.acc_qty.text or '0')
            a_fee = float(self.ids.acc_fee.text or '0')
            if a_qty > 0:
                add_transaction(asset_id, date, a_type, a_price, a_qty, a_fee, '累计')
            self.show_popup("成功", "交易已记录")
        except Exception as e:
            self.show_popup("错误", str(e))

    def show_popup(self, title, msg):
        pop = Popup(title=title, content=Label(text=msg), size_hint=(0.7, 0.3))
        pop.open()

class PriceScreen(Screen):
    def on_enter(self):
        self.update_assets()

    def update_assets(self):
        assets = get_assets()
        self.ids.price_asset_spinner.values = [f"{a[0]} {a[1]}" for a in assets]
        if assets:
            self.ids.price_asset_spinner.text = self.ids.price_asset_spinner.values[0]

    def submit_price(self):
        try:
            selected = self.ids.price_asset_spinner.text
            asset_id = int(selected.split()[0])
            date = self.ids.price_date.text
            price = float(self.ids.price_val.text)
            add_price(asset_id, date, price)
            self.show_popup("成功", "价格已更新")
        except Exception as e:
            self.show_popup("错误", str(e))

    def show_popup(self, title, msg):
        pop = Popup(title=title, content=Label(text=msg), size_hint=(0.7, 0.3))
        pop.open()

class InferScreen(Screen):
    def on_enter(self):
        self.update_assets()

    def update_assets(self):
        assets = get_assets()
        self.ids.infer_asset_spinner.values = [f"{a[0]} {a[1]}" for a in assets]
        if assets:
            self.ids.infer_asset_spinner.text = self.ids.infer_asset_spinner.values[0]
            self.update_cur()

    def update_cur(self, *args):
        selected = self.ids.infer_asset_spinner.text
        if not selected: return
        asset_id = int(selected.split()[0])
        acc = self.ids.infer_account.text
        init_q, acc_q = get_account_holdings(asset_id)
        cur_q = init_q if acc == '初首' else acc_q
        cur_mv = cur_q * get_latest_price(asset_id)
        self.ids.cur_qty.text = str(cur_q)
        self.ids.cur_mv.text = f"{cur_mv:.2f}"

    def calculate(self):
        try:
            old_q = float(self.ids.cur_qty.text)
            old_mv = float(self.ids.cur_mv.text)
            new_q = float(self.ids.new_qty.text)
            new_mv = float(self.ids.new_mv.text)
            if new_q <= old_q or new_mv <= old_mv:
                self.show_popup("错误", "新值必须大于当前")
                return
            added_qty = new_q - old_q
            added_mv = new_mv - old_mv
            avg_price = added_mv / added_qty
            self.ids.infer_result.text = f"新增:{added_qty:.2f}\n均价:{avg_price:.4f}"
            self.calculated_price = avg_price
            self.calculated_qty = added_qty
        except Exception as e:
            self.show_popup("错误", str(e))

    def record(self):
        if not hasattr(self, 'calculated_price'):
            self.show_popup("错误", "请先计算")
            return
        selected = self.ids.infer_asset_spinner.text
        asset_id = int(selected.split()[0])
        acc = self.ids.infer_account.text
        date = datetime.today().strftime('%Y-%m-%d')
        add_transaction(asset_id, date, '买入', self.calculated_price, self.calculated_qty, 0, acc)
        self.show_popup("成功", f"已记录{acc}买入")

    def show_popup(self, title, msg):
        pop = Popup(title=title, content=Label(text=msg), size_hint=(0.7, 0.3))
        pop.open()

class AdjustScreen(Screen):
    def on_enter(self):
        self.update_assets()

    def update_assets(self):
        assets = get_assets()
        self.ids.adjust_asset_spinner.values = [f"{a[0]} {a[1]}" for a in assets]
        if assets:
            self.ids.adjust_asset_spinner.text = self.ids.adjust_asset_spinner.values[0]
            self.on_asset_selected()

    def on_asset_selected(self, *args):
        selected = self.ids.adjust_asset_spinner.text
        if not selected: return
        asset_id = int(selected.split()[0])
        init_q, acc_q = get_account_holdings(asset_id)
        self.ids.cur_init.text = str(init_q)
        self.ids.cur_acc.text = str(acc_q)
        self.ids.new_init.text = str(init_q)
        self.ids.new_acc.text = str(acc_q)

    def apply(self):
        try:
            selected = self.ids.adjust_asset_spinner.text
            asset_id = int(selected.split()[0])
            oi = float(self.ids.cur_init.text)
            oa = float(self.ids.cur_acc.text)
            ni = float(self.ids.new_init.text)
            na = float(self.ids.new_acc.text)
            if abs((ni+na) - (oi+oa)) > 0.001:
                self.show_popup("错误", "总量需保持不变")
                return
            diff = ni - oi
            if abs(diff) < 0.001:
                self.show_popup("提示", "无变化")
                return
            avg = 0
            for h in get_holdings():
                if h['id'] == asset_id:
                    avg = h['avg_cost']
                    break
            date = datetime.today().strftime('%Y-%m-%d')
            if diff > 0:
                add_transaction(asset_id, date, '买入', avg, diff, 0, '初首')
                add_transaction(asset_id, date, '卖出', avg, diff, 0, '累计')
            else:
                pos = -diff
                add_transaction(asset_id, date, '卖出', avg, pos, 0, '初首')
                add_transaction(asset_id, date, '买入', avg, pos, 0, '累计')
            self.show_popup("成功", "账户已调整")
        except Exception as e:
            self.show_popup("错误", str(e))

    def show_popup(self, title, msg):
        pop = Popup(title=title, content=Label(text=msg), size_hint=(0.7, 0.3))
        pop.open()

class AddAssetScreen(Screen):
    def submit_asset(self):
        code = self.ids.code_input.text.strip()
        name = self.ids.name_input.text.strip()
        atype = self.ids.type_spinner.text
        if not code or not name:
            self.show_popup("错误", "代码和名称不能为空")
            return
        try:
            add_asset(code, name, atype)
            self.show_popup("成功", f"已添加 {code} {name}")
        except ValueError as e:
            self.show_popup("错误", str(e))

    def show_popup(self, title, msg):
        pop = Popup(title=title, content=Label(text=msg), size_hint=(0.7, 0.3))
        pop.open()

class HistoryScreen(Screen):
    def on_enter(self):
        self.ids.hist_container.clear_widgets()
        history = get_history()
        for t in history:
            color = (1,0,0,1) if t['profit'] > 0 else (0,1,0,1) if t['profit'] < 0 else (1,1,1,1)
            self.ids.hist_container.add_widget(Label(
                text=f"{t['date']} {t['code']} {t['name']}\n{t['account']} {t['type']} {t['price']}x{t['qty']} 额:{t['amount']} 利:{t['profit']}",
                color=color, size_hint_y=None, height=dp(60)))
            self.ids.hist_container.add_widget(Label(text=" ", size_hint_y=None, height=dp(5)))

class RootWidget(ScreenManager):
    pass

class StockApp(App):
    def build(self):
        init_db()
        return RootWidget()

if __name__ == '__main__':
    StockApp().run()
