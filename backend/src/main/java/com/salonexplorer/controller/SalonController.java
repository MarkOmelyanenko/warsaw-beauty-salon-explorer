package com.salonexplorer.controller;

import com.salonexplorer.dto.SalonDetailsDto;
import com.salonexplorer.dto.SalonListItemDto;
import com.salonexplorer.dto.SalonUpdateRequest;
import com.salonexplorer.service.SalonService;
import jakarta.validation.Valid;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PatchMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.RestController;

import java.util.List;

@RestController
@RequestMapping("/api/salons")
public class SalonController {

    private final SalonService salonService;

    public SalonController(SalonService salonService) {
        this.salonService = salonService;
    }

    @GetMapping
    public List<SalonListItemDto> getSalons(
            @RequestParam(required = false) String district,
            @RequestParam(required = false) String service
    ) {
        return salonService.getSalons(district, service);
    }

    @GetMapping("/{id}")
    public SalonDetailsDto getSalon(@PathVariable Long id) {
        return salonService.getSalonById(id);
    }

    @PatchMapping("/{id}")
    public SalonDetailsDto updateSalon(
            @PathVariable Long id,
            @Valid @RequestBody SalonUpdateRequest request
    ) {
        return salonService.updateSalon(id, request);
    }
}
