#!/usr/bin/env python3
"""
Script unificado para processar todos os arquivos .txt de dados PMU
e gerar os CSVs finais limpos em data/csv_final/.

Pipeline (por arquivo .txt):
  1. Extrai linhas CSV entre marcadores START_OF_CSV_DATA / END_OF_CSV_DATA
  2. Salva o CSV limpo em data/csv_final/
  3. Salva o CSV limpo em data/csv_final/

Suporta dois formatos de entrada:
  - Antigo (8 colunas):  CORE_ID,TIMESTAMP,...,LABEL
  - Novo  (11 colunas): CORE_ID,TIMESTAMP,...,LABEL,DET_STATUS,DET_PROB,BENCH_ID

Uso:
  python3 process_all.py                  # processa todos os .txt na pasta data/
  python3 process_all.py data1.txt        # processa apenas o arquivo especificado
"""

import sys
import os
import glob


# Formatos suportados (mantém CORE_ID na saída)
COLUMNS_OLD = ["CORE_ID", "TIMESTAMP", "CPU_CYCLES", "INSTRUCTIONS", "CACHE_MISSES", "BRANCH_MISSES", "L2_CACHE_ACCESS", "LABEL"]
COLUMNS_NEW = ["CORE_ID", "TIMESTAMP", "CPU_CYCLES", "INSTRUCTIONS", "CACHE_MISSES", "BRANCH_MISSES", "L2_CACHE_ACCESS", "LABEL", "DET_STATUS", "DET_PROB", "BENCH_ID"]
COLUMNS_EENN = ["CORE_ID", "TIMESTAMP", "CPU_CYCLES", "INSTRUCTIONS", "CACHE_MISSES", "BRANCH_MISSES", "L2_CACHE_ACCESS", "LABEL", "DET_STATUS", "DET_PROB", "BENCH_ID", "EXIT_USED", "CYCLES_SPENT"]

HEADER_OLD = "CORE_ID,TIMESTAMP,CPU_CYCLES,INSTRUCTIONS,CACHE_MISSES,BRANCH_MISSES,L2_CACHE_ACCESS,LABEL"
HEADER_NEW = "CORE_ID,TIMESTAMP,CPU_CYCLES,INSTRUCTIONS,CACHE_MISSES,BRANCH_MISSES,L2_CACHE_ACCESS,LABEL,DET_STATUS,DET_PROB,BENCH_ID"
HEADER_EENN = "CORE_ID,TIMESTAMP,CPU_CYCLES,INSTRUCTIONS,CACHE_MISSES,BRANCH_MISSES,L2_CACHE_ACCESS,LABEL,DET_STATUS,DET_PROB,BENCH_ID,EXIT_USED,CYCLES_SPENT"

VALID_CORES = {'1', '2', '3'}


def process_txt_to_clean_csv(input_file, output_file):
    """
    Lê um arquivo .txt bruto com dados PMU e gera diretamente o CSV final limpo.
    Auto-detecta o formato (8, 11 ou 13 colunas) a partir do cabeçalho CSV.
    """
    print(f"\n{'='*60}")
    print(f"  Processando: {os.path.basename(input_file)}")
    print(f"  Saída:       {os.path.basename(output_file)}")
    print(f"{'='*60}")

    in_csv = False
    lines_written = 0
    label_counts = {}
    bench_id_counts = {}
    detected_format = None  # 'old', 'new' or 'eenn'
    expected_cols = None
    output_columns = None
    header_written = False

    with open(input_file, 'r', errors='replace') as fin, open(output_file, 'w') as fout:
        for line in fin:
            stripped = line.strip()

            # Detecta início/fim de bloco CSV
            if stripped == "START_OF_CSV_DATA":
                in_csv = True
                continue
            elif stripped == "END_OF_CSV_DATA":
                in_csv = False
                continue

            if not in_csv:
                continue

            # Ignora linhas vazias
            if stripped == "":
                continue

            # Detecta formato a partir do cabeçalho
            if stripped.startswith("CORE_ID"):
                if "EXIT_USED" in stripped:
                    detected_format = 'eenn'
                    expected_cols = 13
                    output_columns = COLUMNS_EENN
                elif "BENCH_ID" in stripped:
                    detected_format = 'new'
                    expected_cols = 11
                    output_columns = COLUMNS_NEW
                else:
                    detected_format = 'old'
                    expected_cols = 8
                    output_columns = COLUMNS_OLD

                # Escreve cabeçalho apenas uma vez
                if not header_written:
                    fout.write(','.join(output_columns) + '\n')
                    header_written = True
                continue

            parts = stripped.split(',')

            # Valida número de colunas e CORE_ID válido
            if len(parts) != expected_cols or parts[0] not in VALID_CORES:
                continue

            # Mantém todas as colunas (incluindo CORE_ID)
            fout.write(stripped + '\n')
            lines_written += 1

            # Contagem de labels para diagnóstico
            label = parts[7].strip()
            label_counts[label] = label_counts.get(label, 0) + 1

            # Contagem de BENCH_ID (formato novo/eenn)
            if detected_format in ('new', 'eenn') and len(parts) >= 11:
                bench_id = parts[10].strip()
                bench_id_counts[bench_id] = bench_id_counts.get(bench_id, 0) + 1

    # Se nenhum header foi encontrado, escrever header padrão (old)
    if not header_written:
        print(f"  ⚠ Nenhum bloco CSV encontrado no arquivo!")

    fmt_str = f"({detected_format}, {expected_cols} cols)" if detected_format else "(não detectado)"
    print(f"  Formato:  {fmt_str}")
    print(f"  ✓ {lines_written} linhas escritas")
    if label_counts:
        print(f"  Distribuição de labels:")
        for label, cnt in sorted(label_counts.items()):
            print(f"    Label {label}: {cnt} amostras")
    if bench_id_counts:
        print(f"  Distribuição de BENCH_ID:")
        for bid, cnt in sorted(bench_id_counts.items()):
            print(f"    BENCH_ID {bid}: {cnt} amostras")

    return lines_written, label_counts


def main():
    # Diretório base onde ficam os dados
    script_dir = os.path.dirname(os.path.abspath(__file__))

    # Pasta de saída para os CSVs finais
    output_dir = os.path.join(script_dir, 'csv_final')
    os.makedirs(output_dir, exist_ok=True)

    # Determina quais arquivos processar
    if len(sys.argv) > 1:
        # Argumentos fornecidos: processa apenas os arquivos especificados
        txt_files = []
        for arg in sys.argv[1:]:
            path = arg if os.path.isabs(arg) else os.path.join(script_dir, arg)
            if os.path.exists(path):
                txt_files.append(path)
            else:
                print(f"⚠ Arquivo não encontrado: {arg}")
    else:
        # Sem argumentos: processa todos os .txt na pasta data/
        txt_files = sorted(glob.glob(os.path.join(script_dir, '*.txt')))

    if not txt_files:
        print("Nenhum arquivo .txt encontrado para processar.")
        sys.exit(1)

    print(f"\n🔄 Processando {len(txt_files)} arquivo(s) .txt → csv_final/\n")

    total_lines = 0
    processed = 0
    total_label_counts = {}

    for txt_path in txt_files:
        basename = os.path.basename(txt_path)
        # data1.txt → data1_clean.csv
        csv_name = os.path.splitext(basename)[0] + '_clean.csv'
        csv_path = os.path.join(output_dir, csv_name)

        lines, file_label_counts = process_txt_to_clean_csv(txt_path, csv_path)
        total_lines += lines
        processed += 1
        for label, count in file_label_counts.items():
            total_label_counts[label] = total_label_counts.get(label, 0) + count

    print(f"\n{'='*60}")
    print(f"  ✅ Concluído! {processed} arquivo(s) processado(s)")
    print(f"  📊 Total de linhas: {total_lines}")
    print(f"  📁 CSVs salvos em: {output_dir}/")
    if total_label_counts:
        print(f"  📈 Distribuição total de labels (todos os arquivos):")
        for label, cnt in sorted(total_label_counts.items()):
            print(f"    Label {label}: {cnt} amostras")
    print(f"{'='*60}\n")


if __name__ == '__main__':
    main()

