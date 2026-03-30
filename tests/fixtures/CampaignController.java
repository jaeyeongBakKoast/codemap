package com.example.campaign;

import org.springframework.web.bind.annotation.*;
import java.util.List;

@RestController
@RequestMapping("/api/campaigns")
public class CampaignController {

    private final CampaignService campaignService;

    public CampaignController(CampaignService campaignService) {
        this.campaignService = campaignService;
    }

    @GetMapping
    public ResultResponse<List<CampaignResponse>> getCampaigns() {
        return campaignService.findAll();
    }

    @GetMapping("/{id}")
    public ResultResponse<CampaignResponse> getCampaign(@PathVariable Long id) {
        return campaignService.findById(id);
    }
}
