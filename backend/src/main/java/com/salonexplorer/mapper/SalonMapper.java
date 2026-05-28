package com.salonexplorer.mapper;

import com.salonexplorer.dto.SalonDetailsDto;
import com.salonexplorer.dto.SalonListItemDto;
import com.salonexplorer.dto.SalonUpdateRequest;
import com.salonexplorer.model.Salon;
import org.springframework.stereotype.Component;

import java.util.ArrayList;

@Component
public class SalonMapper {

    public SalonListItemDto toListItemDto(Salon salon) {
        SalonListItemDto dto = new SalonListItemDto();
        dto.setId(salon.getId());
        dto.setName(salon.getName());
        dto.setDistrict(salon.getDistrict());
        dto.setRating(salon.getRating());
        dto.setReviewCount(salon.getReviewCount());
        dto.setPriceRange(salon.getPriceRange());
        return dto;
    }

    public SalonDetailsDto toDetailsDto(Salon salon) {
        SalonDetailsDto dto = new SalonDetailsDto();
        dto.setId(salon.getId());
        dto.setName(salon.getName());
        dto.setAddress(salon.getAddress());
        dto.setDistrict(salon.getDistrict());
        dto.setPhone(salon.getPhone());
        dto.setWebsiteUrl(salon.getWebsiteUrl());
        dto.setServices(new ArrayList<>(salon.getServices()));
        dto.setPriceRange(salon.getPriceRange());
        dto.setRating(salon.getRating());
        dto.setReviewCount(salon.getReviewCount());
        dto.setSource(salon.getSource());
        dto.setExternalId(salon.getExternalId());
        dto.setCreatedAt(salon.getCreatedAt());
        dto.setUpdatedAt(salon.getUpdatedAt());
        return dto;
    }

    public void updateEntity(Salon salon, SalonUpdateRequest request) {
        if (request.getName() != null) {
            salon.setName(request.getName());
        }
        if (request.getAddress() != null) {
            salon.setAddress(request.getAddress());
        }
        if (request.getDistrict() != null) {
            salon.setDistrict(request.getDistrict());
        }
        if (request.getPhone() != null) {
            salon.setPhone(request.getPhone());
        }
        if (request.getWebsiteUrl() != null) {
            salon.setWebsiteUrl(request.getWebsiteUrl());
        }
        if (request.getServices() != null) {
            salon.setServices(request.getServices());
        }
        if (request.getPriceRange() != null) {
            salon.setPriceRange(request.getPriceRange());
        }
        if (request.getRating() != null) {
            salon.setRating(request.getRating());
        }
        if (request.getReviewCount() != null) {
            salon.setReviewCount(request.getReviewCount());
        }
    }
}
