struct Cell {
    int filled_units;
// Ось соседа == world_age % 3
// Количество заявок в соседа 0
    int plan_count_0;
// Количество заявок в соседа 1
    int plan_count_1;
};


// Look-Up Table - таблица поиска для вычислеия сдвига кривой Мортона
// Полный контроль "над кривой Мортона" позволит точно расположить данные для одного вычислительного блока близко (что делать с подгружаемым слоем соседей в одну ячейку?)
// Переписть ячейки и юниты на буферы
Cell new_cell() {
    return Cell(0, 0, 0);
}


Cell unpack_cell(uvec4 packed_cell) {
    Cell cell;

    cell.filled_units = int(bitfieldExtract(packed_cell.r, 0, 6));
    cell.plan_count_0 = int(bitfieldExtract(packed_cell.r, 6, 6));
    cell.plan_count_1 = int(bitfieldExtract(packed_cell.r, 12, 6));

    return cell;
}


uvec4 pack_cell(Cell cell) {
    uvec4 packed_cell = uvec4(0);

    packed_cell.r = uint(cell.filled_units);
    packed_cell.r = bitfieldInsert(packed_cell.r, uint(cell.plan_count_0), 6, 6);
    packed_cell.r = bitfieldInsert(packed_cell.r, uint(cell.plan_count_1), 12, 6);

    return packed_cell;
}
