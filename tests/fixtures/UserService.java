package com.example.user;

import org.springframework.stereotype.Service;

@Service
public class UserService {

    private final UserRepository userRepository;
    private final EmailService emailService;

    public UserService(UserRepository userRepository, EmailService emailService) {
        this.userRepository = userRepository;
        this.emailService = emailService;
    }

    public List<User> findAll() {
        return userRepository.findAll();
    }

    public User create(User user) {
        User saved = userRepository.save(user);
        emailService.sendWelcome(saved);
        return saved;
    }

    public User findById(Long id) {
        return userRepository.findById(id);
    }
}
