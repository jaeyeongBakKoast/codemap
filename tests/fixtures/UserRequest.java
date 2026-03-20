package com.example.user;

import lombok.*;

@Getter
@Setter
@NoArgsConstructor
@AllArgsConstructor
public class UserRequest {

    // 이메일 주소
    private String email;
    // 사용자명
    private String name;
}
