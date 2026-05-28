package com.salonexplorer.service;

import com.salonexplorer.dto.SalonDetailsDto;
import com.salonexplorer.dto.SalonListItemDto;
import com.salonexplorer.dto.SalonUpdateRequest;
import com.salonexplorer.exception.NotFoundException;
import com.salonexplorer.mapper.SalonMapper;
import com.salonexplorer.model.Salon;
import com.salonexplorer.repository.SalonRepository;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.util.List;
import java.util.Locale;
import java.util.stream.Stream;

@Service
@Transactional(readOnly = true)
public class SalonService {

    private final SalonRepository salonRepository;
    private final SalonMapper salonMapper;

    public SalonService(SalonRepository salonRepository, SalonMapper salonMapper) {
        this.salonRepository = salonRepository;
        this.salonMapper = salonMapper;
    }

    public List<SalonListItemDto> getSalons(String district, String service) {
        Stream<Salon> salons = salonRepository.findAll().stream();

        if (hasText(district)) {
            String districtValue = district.trim().toLowerCase(Locale.ROOT);
            salons = salons.filter(salon -> districtValue.equals(normalize(salon.getDistrict())));
        }

        if (hasText(service)) {
            String serviceValue = service.trim().toLowerCase(Locale.ROOT);
            salons = salons.filter(salon -> salon.getServices().stream()
                    .anyMatch(salonService -> normalize(salonService).contains(serviceValue)));
        }

        return salons.map(salonMapper::toListItemDto).toList();
    }

    public SalonDetailsDto getSalonById(Long id) {
        Salon salon = findSalonOrThrow(id);
        return salonMapper.toDetailsDto(salon);
    }

    @Transactional
    public SalonDetailsDto updateSalon(Long id, SalonUpdateRequest request) {
        validateUpdateRequest(request);
        Salon salon = findSalonOrThrow(id);
        salonMapper.updateEntity(salon, request);
        Salon saved = salonRepository.save(salon);
        return salonMapper.toDetailsDto(saved);
    }

    private void validateUpdateRequest(SalonUpdateRequest request) {
        if (request.getName() != null && request.getName().isBlank()) {
            throw new IllegalArgumentException("name must not be blank");
        }
        if (request.getAddress() != null && request.getAddress().isBlank()) {
            throw new IllegalArgumentException("address must not be blank");
        }
        if (request.getDistrict() != null && request.getDistrict().isBlank()) {
            throw new IllegalArgumentException("district must not be blank");
        }
    }

    private Salon findSalonOrThrow(Long id) {
        return salonRepository.findById(id)
                .orElseThrow(() -> new NotFoundException("Salon not found with id: " + id));
    }

    private static boolean hasText(String value) {
        return value != null && !value.isBlank();
    }

    private static String normalize(String value) {
        return value == null ? null : value.toLowerCase(Locale.ROOT);
    }
}
