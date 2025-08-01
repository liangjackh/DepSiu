// 测试用例：包含多种always block和赋值类型的SystemVerilog模块
module test_always_blocks (
    input wire clk,
    input wire reset,
    input wire [7:0] data_in,
    output reg [7:0] data_out,
    output wire [7:0] comb_out
);

    reg [7:0] counter;
    reg [7:0] register_a;
    reg [7:0] register_b;
    reg [7:0] register_c;
    reg state;

    // Always FF block - 时序逻辑，使用非阻塞赋值
    always_ff @(posedge clk or posedge reset) begin
        if (reset) begin
            counter <= 8'b0;
            register_a <= 8'b0;
            data_out <= 8'b0;
            state <= 1'b0;
        end else begin
            counter <= counter + 1;
            register_a <= data_in;
            data_out <= register_a;
            state <= ~state;
        end
    end

    // Always Comb block - 组合逻辑，使用阻塞赋值
    always_comb begin
        if (state) begin
            register_b = register_a + counter;
        end else begin
            register_b = register_a - counter;
        end
    end

    // 连续赋值
    assign comb_out = register_b;

    // 传统always block - 用不同的寄存器避免冲突
    always @(*) begin
        case (data_in[1:0])
            2'b00: register_c = 8'h00;
            2'b01: register_c = 8'hFF;
            2'b10: register_c = data_in;
            default: register_c = register_a;
        endcase
    end

endmodule