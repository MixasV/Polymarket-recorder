#!/usr/bin/env python3
"""
Найти и удалить глитчи из БД market_snapshots.

Критерии глитчей:
1. Bid = Ask (спред = 0 или <= $0.001)
2. UP и DOWN равны при >$0.6 (не считая $0.5)
3. Резкие скачки: цена меняется >$0.2 за <2 секунды, потом возвращается
4. Аномально низкие цены: UP ask или DOWN ask < $0.04
5. UP + DOWN сумма < 0.95 или > 1.15

Глитчи УДАЛЯЮТСЯ, а не интерполируются, так как:
- Интерполяция создаёт искусственные данные
- Удаление сохраняет реальность данных
- Рынки записываются каждую секунду, потеря нескольких снапшотов не критична
"""
import sqlite3
import pandas as pd
import numpy as np
from pathlib import Path
from datetime import datetime

DB_PATH = Path(__file__).parent.parent / '15m-synthetic' / 'db' / 'real-data.db'

def find_glitches(conn):
    """Найти все глитчи в БД"""
    print("Загрузка данных из БД...")
    
    # Загрузить все снапшоты (включая глитчи с bid=0)
    df = pd.read_sql_query("""
        SELECT rowid as id, market_slug, dt, 
               up_bid, up_ask, up_mid,
               down_bid, down_ask, down_mid,
               time_to_expiry
        FROM market_snapshots
        WHERE up_ask > 0 AND down_ask > 0
        ORDER BY market_slug, dt ASC
    """, conn)
    
    print(f"Загружено {len(df)} снапшотов")
    
    df['ts'] = pd.to_datetime(df['dt'], format='ISO8601').astype('int64') // 10**9
    
    glitches = []
    
    print("\nПоиск глитчей...")
    
    # Группируем по рынкам для анализа временных рядов
    for market_slug, group in df.groupby('market_slug'):
        group = group.sort_values('ts').copy()
        
        for idx in group.index:
            row = group.loc[idx]
            rowid = int(row['id'])
            
            # ГЛИТЧ 1: Аномально низкие цены (< $0.04) - ПРОВЕРЯЕМ ПЕРВЫМ!
            # Нормальная цена не может быть $0.001-0.03
            if row['up_ask'] < 0.04 or row['down_ask'] < 0.04:
                glitches.append({
                    'rowid': rowid,
                    'market_slug': market_slug,
                    'dt': row['dt'],
                    'type': 'anomaly_low_price',
                    'details': f"UP ask=${row['up_ask']:.3f}, DOWN ask=${row['down_ask']:.3f}",
                })
                continue  # Не проверяем другие критерии для этого снапшота
            
            # ГЛИТЧ 2: Bid = Ask (спред = 0 или очень маленький)
            if abs(row['up_bid'] - row['up_ask']) <= 0.001 or abs(row['down_bid'] - row['down_ask']) <= 0.001:
                glitches.append({
                    'rowid': rowid,
                    'market_slug': market_slug,
                    'dt': row['dt'],
                    'type': 'zero_spread',
                    'details': f"UP bid=${row['up_bid']:.3f} ask=${row['up_ask']:.3f}, DOWN bid=${row['down_bid']:.3f} ask=${row['down_ask']:.3f}",
                })
                continue
            
            # ГЛИТЧ 3: UP и DOWN равны при >$0.6 (не считая $0.5)
            up_mid = row['up_mid']
            down_mid = row['down_mid']
            
            if abs(up_mid - down_mid) < 0.05 and up_mid > 0.6:
                glitches.append({
                    'rowid': rowid,
                    'market_slug': market_slug,
                    'dt': row['dt'],
                    'type': 'equal_prices',
                    'details': f"UP mid=${up_mid:.3f}, DOWN mid=${down_mid:.3f}",
                })
                continue
            
            # ГЛИТЧ 4: UP + DOWN сумма неправильная
            # Используем ask цены (цены покупки), так как они важнее для нас
            total = row['up_ask'] + row['down_ask']
            
            # Сумма должна быть от $0.95 до $1.15 (обычно >$1 из-за спреда)
            if total < 0.95 or total > 1.15:
                glitches.append({
                    'rowid': rowid,
                    'market_slug': market_slug,
                    'dt': row['dt'],
                    'type': 'invalid_sum',
                    'details': f"UP ask=${row['up_ask']:.3f} + DOWN ask=${row['down_ask']:.3f} = ${total:.3f}",
                })
                continue
            
            # ГЛИТЧ 5: Резкие скачки (проверяем только если есть предыдущий и следующий снапшот)
            group_list = group.index.tolist()
            idx_pos = group_list.index(idx)
            
            if idx_pos > 0 and idx_pos < len(group_list) - 1:
                prev_idx = group_list[idx_pos - 1]
                next_idx = group_list[idx_pos + 1]
                
                prev = group.loc[prev_idx]
                next_row = group.loc[next_idx]
                
                # Проверяем временной интервал
                dt_prev = row['ts'] - prev['ts']
                dt_next = next_row['ts'] - row['ts']
                
                if dt_prev < 2 and dt_next < 2:  # В пределах 2 секунд
                    # Проверяем DOWN ask (самая важная цена для нас)
                    down_ask_change_in = abs(row['down_ask'] - prev['down_ask'])
                    down_ask_change_out = abs(next_row['down_ask'] - row['down_ask'])
                    
                    # Если цена скакнула >$0.2, потом вернулась (увеличен порог с $0.1 до $0.2)
                    if down_ask_change_in > 0.2 and down_ask_change_out > 0.2:
                        # Проверяем, что до и после цены похожи
                        if abs(prev['down_ask'] - next_row['down_ask']) < 0.1:
                            glitches.append({
                                'rowid': rowid,
                                'market_slug': market_slug,
                                'dt': row['dt'],
                                'type': 'spike',
                                'details': f"DOWN ask: {prev['down_ask']:.3f} -> {row['down_ask']:.3f} -> {next_row['down_ask']:.3f}",
                            })
                            continue
                    
                    # Также проверяем UP ask
                    up_ask_change_in = abs(row['up_ask'] - prev['up_ask'])
                    up_ask_change_out = abs(next_row['up_ask'] - row['up_ask'])
                    
                    if up_ask_change_in > 0.2 and up_ask_change_out > 0.2:
                        if abs(prev['up_ask'] - next_row['up_ask']) < 0.1:
                            glitches.append({
                                'rowid': rowid,
                                'market_slug': market_slug,
                                'dt': row['dt'],
                                'type': 'spike',
                                'details': f"UP ask: {prev['up_ask']:.3f} -> {row['up_ask']:.3f} -> {next_row['up_ask']:.3f}",
                            })
    
    return pd.DataFrame(glitches)


def delete_glitches(conn, glitches_df, dry_run=True):
    """Удалить глитчи из БД"""
    if len(glitches_df) == 0:
        print("Нет глитчей для удаления")
        return
    
    print(f"\n{'='*100}")
    print(f"УДАЛЕНИЕ ГЛИТЧЕЙ ({'DRY RUN' if dry_run else 'РЕАЛЬНОЕ'})")
    print(f"{'='*100}")
    
    cursor = conn.cursor()
    
    # Проверяем текущее количество снапшотов
    cursor.execute("SELECT COUNT(*) FROM market_snapshots")
    total_before = cursor.fetchone()[0]
    print(f"\nСнапшотов в БД до удаления: {total_before}")
    print(f"Глитчей к удалению: {len(glitches_df)}")
    
    if not dry_run:
        # Удаляем глитчи
        deleted = 0
        for idx, glitch in glitches_df.iterrows():
            market_slug = glitch['market_slug']
            dt = glitch['dt']
            
            cursor.execute("""
                DELETE FROM market_snapshots
                WHERE market_slug = ? AND dt = ?
            """, (market_slug, dt))
            
            deleted += cursor.rowcount
            
            if (idx + 1) % 1000 == 0:
                print(f"  Удалено {idx + 1}/{len(glitches_df)} глитчей...")
        
        conn.commit()
        
        # Проверяем результат
        cursor.execute("SELECT COUNT(*) FROM market_snapshots")
        total_after = cursor.fetchone()[0]
        
        print(f"\n✅ Удалено {deleted} глитчей")
        print(f"Снапшотов в БД после удаления: {total_after}")
        print(f"Разница: {total_before - total_after}")
        
        # Проверяем, что рынки остались целыми
        cursor.execute("""
            SELECT market_slug, COUNT(*) as count
            FROM market_snapshots
            GROUP BY market_slug
            HAVING count < 100
            ORDER BY count
        """)
        
        small_markets = cursor.fetchall()
        if small_markets:
            print(f"\n⚠️  Рынков с <100 снапшотов: {len(small_markets)}")
            print("Первые 10:")
            for market, count in small_markets[:10]:
                print(f"  {market}: {count} снапшотов")
        else:
            print(f"\n✅ Все рынки имеют достаточно снапшотов")
    else:
        print(f"\n(DRY RUN: изменения не применены)")
        print(f"Будет удалено: {len(glitches_df)} снапшотов")
        print(f"Останется: {total_before - len(glitches_df)} снапшотов")


def main():
    print("="*100)
    print("ПОИСК И УДАЛЕНИЕ ГЛИТЧЕЙ ИЗ БД")
    print("="*100)
    
    conn = sqlite3.connect(DB_PATH)
    
    # Найти глитчи
    glitches_df = find_glitches(conn)
    
    print(f"\n{'='*100}")
    print(f"НАЙДЕНО ГЛИТЧЕЙ: {len(glitches_df)}")
    print(f"{'='*100}")
    
    if len(glitches_df) > 0:
        # Статистика по типам
        print("\nПо типам:")
        for glitch_type, count in glitches_df['type'].value_counts().items():
            print(f"  {glitch_type}: {count}")
        
        # Сохранить в CSV
        csv_path = 'glitches_found.csv'
        glitches_df.to_csv(csv_path, index=False)
        print(f"\n[OK] Глитчи сохранены в {csv_path}")
        
        # Показать первые 20 глитчей
        print(f"\nПервые 20 глитчей:")
        print(f"{'#':<5} {'Тип':<15} {'Рынок':<30} {'Время':<30} {'Детали':<50}")
        print("-"*130)
        
        for idx, glitch in glitches_df.head(20).iterrows():
            print(f"{idx+1:<5} {glitch['type']:<15} {glitch['market_slug'][-30:]:<30} "
                  f"{glitch['dt'][-30:]:<30} {glitch['details']:<50}")
        
        # Спросить, удалять ли
        print(f"\n{'='*100}")
        response = input(f"Удалить {len(glitches_df)} глитчей? (yes/no/dry-run): ").strip().lower()
        
        if response == 'yes':
            delete_glitches(conn, glitches_df, dry_run=False)
        elif response == 'dry-run':
            delete_glitches(conn, glitches_df, dry_run=True)
        else:
            print("Отменено")
    
    conn.close()


if __name__ == '__main__':
    main()
