// 测试用的SystemVerilog模块
module counter(
    input wire clk,
    input wire reset,
    input wire enable,
    output reg [7:0] count
);

    // 连续赋值
    wire reset_sync = reset & clk;
    
    // 时序always块
    always @(posedge clk or posedge reset) begin
        if (reset) begin
            count <= 8'b0;
        end else if (enable) begin
            count <= count + 1;
        end
    end
    
    // 组合逻辑always块
    reg overflow;
    always @(*) begin
        if (count == 8'hFF)
            overflow = 1'b1;
        else
            overflow = 1'b0;
    end
    
    // 状态机示例
    typedef enum logic [1:0] {
        IDLE = 2'b00,
        COUNT = 2'b01,
        STOP = 2'b10
    } state_t;
    
    state_t current_state, next_state;
    
    // 状态寄存器
    always @(posedge clk or posedge reset) begin
        if (reset)
            current_state <= IDLE;
        else
            current_state <= next_state;
    end
    
    // 次态逻辑
    always @(*) begin
        case (current_state)
            IDLE: begin
                if (enable)
                    next_state = COUNT;
                else
                    next_state = IDLE;
            end
            COUNT: begin
                if (count == 8'hFE)
                    next_state = STOP;
                else
                    next_state = COUNT;
            end
            STOP: begin
                next_state = IDLE;
            end
            default: next_state = IDLE;
        endcase
    end
    
    // for循环示例
    integer i;
    reg [7:0] temp_array [0:7];
    
    always @(posedge clk) begin
        for (i = 0; i < 8; i = i + 1) begin
            temp_array[i] <= count + i;
        end
    end

endmodule

// 另一个模块示例
module top_module(
    input wire clk,
    input wire reset
);

    wire enable = 1'b1;
    wire [7:0] counter_out;
    
    // 实例化计数器
    counter u_counter(
        .clk(clk),
        .reset(reset),
        .enable(enable),
        .count(counter_out)
    );
    
    // while循环示例
    integer j;
    always @(posedge clk) begin
        j = 0;
        while (j < 4) begin
            // 一些操作
            j = j + 1;
        end
    end

endmodule