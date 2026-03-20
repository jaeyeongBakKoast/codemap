package com.example.user;

import lombok.*;
import java.time.LocalDateTime;

@Getter
@Setter
@NoArgsConstructor
@AllArgsConstructor
public class User {

    // 사용자 고유번호
    private Long id;
    // 이메일 주소
    private String email;
    // 사용자명
    private String name;
    // 소속 부서 ID
    private Long deptId;
    // 등록일
    private LocalDateTime createdAt;
}
