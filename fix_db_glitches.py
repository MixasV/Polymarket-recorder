#!/usr/bin/env python3
"""
Найти и исправить глитчи в БД market_snapshots.

Критерии глитчей:
1. bid = ask (спред = 0) - когда цена последней сделки записана как bid и ask
2. UP + DOWN становятся равными при >$0.6 (не считая $0.5)
3. Резкие скачки: цена меняется >$0.6 за <1 секунду, потом возвращается
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
    
    # Загрузить снапшоты за март 2026 (когда были реальные сделки)
    df = pd.read_sql_query("""
        SELECT rowid as id, market_slug, dt, 
               up_bid, up_ask, up_mid,
               down_bid, down_ask, down_mid,
               time_to_expiry
        FROM market_snapshots
        WHERE up_bid > 0 AND up_ask > 0 AND down_bid > 0 AND down_ask > 0
          AND dt >= '2026-03-01' AND dt < '2026-04-01'
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
            
            # ГЛИТЧ 1: UP и DOWN равны при >$0.6 (не считая $0.5)
            up_mid = row['up_mid']
            down_mid = row['down_mid']
            
            if abs(up_mid - down_mid) < 0.05 and up_mid > 0.6:
                glitches.append({
                    'rowid': rowid,
                    'market_slug': market_slug,
                    'dt': row['dt'],
                    'type': 'equal_prices',
                    'details': f"UP mid=${up_mid:.3f}, DOWN mid=${down_mid:.3f}",
                    'up_bid': row['up_bid'],
                    'up_ask': row['up_ask'],
                    'down_bid': row['down_bid'],
                    'down_ask': row['down_ask'],
                })
            
            # ГЛИТЧ 2: UP + DOWN сумма неправильная
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
                    'up_bid': row['up_bid'],
                    'up_ask': row['up_ask'],
                    'down_bid': row['down_bid'],
                    'down_ask': row['down_ask'],
                })
            
            # ГЛИТЧ 3: Резкие скачки (проверяем только если есть предыдущий и следующий снапшот)
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
                    
                    # Если цена скакнула >$0.6, потом вернулась
                    if down_ask_change_in > 0.6 and down_ask_change_out > 0.6:
                        # Проверяем, что до и после цены похожи
                        if abs(prev['down_ask'] - next_row['down_ask']) < 0.1:
                            glitches.append({
                                'rowid': rowid,
                                'market_slug': market_slug,
                                'dt': row['dt'],
                                'type': 'spike',
                                'details': f"DOWN ask: {prev['down_ask']:.3f} -> {row['down_ask']:.3f} -> {next_row['down_ask']:.3f}",
                                'up_bid': row['up_bid'],
                                'up_ask': row['up_ask'],
                                'down_bid': row['down_bid'],
                                'down_ask': row['down_ask'],
                            })
    
    return pd.DataFrame(glitches)


def fix_glitches(conn, glitches_df, dry_run=True, limit=None):
    """Исправить глитчи в БД"""
    if len(glitches_df) == 0:
        print("Нет глитчей для исправления")
        return
    
    if limit:
        glitches_df = glitches_df.head(limit)
    
    print(f"\n{'='*100}")
    print(f"ИСПРАВЛЕНИЕ ГЛИТЧЕЙ ({'DRY RUN' if dry_run else 'РЕАЛЬНОЕ'})")
    print(f"{'='*100}")
    
    cursor = conn.cursor()
    fixed_count = 0
    
    for idx, glitch in glitches_df.iterrows():
        rowid = glitch['rowid']
        market_slug = glitch['market_slug']
        
        # Получить соседние снапшоты для интерполяции
        cursor.execute("""
            SELECT rowid, dt, up_bid, up_ask, down_bid, down_ask
            FROM market_snapshots
            WHERE market_slug = ?
              AND rowid < ?
              AND up_bid > 0 AND up_ask > 0 AND down_bid > 0 AND down_ask > 0
            ORDER BY rowid DESC
            LIMIT 1
        """, (market_slug, rowid))
        prev_row = cursor.fetchone()
        
        cursor.execute("""
            SELECT rowid, dt, up_bid, up_ask, down_bid, down_ask
            FROM market_snapshots
            WHERE market_slug = ?
              AND rowid > ?
              AND up_bid > 0 AND up_ask > 0 AND down_bid > 0 AND down_ask > 0
            ORDER BY rowid ASC
            LIMIT 1
        """, (market_slug, rowid))
        next_row = cursor.fetchone()
        
        if prev_row and next_row:
            # Интерполяция: среднее между предыдущим и следующим
            new_up_bid = (prev_row[2] + next_row[2]) / 2
            new_up_ask = (prev_row[3] + next_row[3]) / 2
            new_down_bid = (prev_row[4] + next_row[4]) / 2
            new_down_ask = (prev_row[5] + next_row[5]) / 2
            new_up_mid = (new_up_bid + new_up_ask) / 2
            new_down_mid = (new_down_bid + new_down_ask) / 2
            
            print(f"\nГлитч #{idx+1} ({glitch['type']}):")
            print(f"  Рынок: {market_slug}")
            print(f"  Время: {glitch['dt']}")
            print(f"  Было: UP bid=${glitch['up_bid']:.3f} ask=${glitch['up_ask']:.3f}, "
                  f"DOWN bid=${glitch['down_bid']:.3f} ask=${glitch['down_ask']:.3f}")
            print(f"  Стало: UP bid=${new_up_bid:.3f} ask=${new_up_ask:.3f}, "
                  f"DOWN bid=${new_down_bid:.3f} ask=${new_down_ask:.3f}")
            
            if not dry_run:
                cursor.execute("""
                    UPDATE market_snapshots
                    SET up_bid = ?, up_ask = ?, up_mid = ?,
                        down_bid = ?, down_ask = ?, down_mid = ?
                    WHERE rowid = ?
                """, (new_up_bid, new_up_ask, new_up_mid,
                      new_down_bid, new_down_ask, new_down_mid, rowid))
                fixed_count += 1
        else:
            print(f"\n[!] Не могу исправить глитч #{idx+1}: нет соседних снапшотов")
    
    if not dry_run:
        conn.commit()
        print(f"\n[OK] Исправлено {fixed_count} глитчей")
    else:
        print(f"\n(DRY RUN: изменения не применены)")


def main():
    print("="*100)
    print("ПОИСК И ИСПРАВЛЕНИЕ ГЛИТЧЕЙ В БД")
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
        
        # Спросить, исправлять ли
        print(f"\n{'='*100}")
        response = input(f"Исправить {len(glitches_df)} глитчей? (yes/no/dry-run): ").strip().lower()
        
        if response == 'yes':
            fix_glitches(conn, glitches_df, dry_run=False)
        elif response == 'dry-run':
            fix_glitches(conn, glitches_df, dry_run=True, limit=10)
        else:
            print("Отменено")
    
    conn.close()


if __name__ == '__main__':
    main()
